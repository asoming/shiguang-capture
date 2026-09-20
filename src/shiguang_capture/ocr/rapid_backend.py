"""Offline OCR with verified models and image-based line reconstruction."""
from __future__ import annotations
import logging
import re
import statistics
import time
from importlib.resources import files
from .base import OCRResult
from ..structured import bounds, code_from_blocks, text_from_blocks, TableData, detect_grid

log = logging.getLogger(__name__)
MODEL_VERSION = 'PP-OCRv5 mobile zh/en; PP-OCRv4 detector; RapidOCR 1.4.4'


def _rows(blocks):
    entries = [(bounds(block), block) for block in blocks if bounds(block)]
    if not entries:
        return []
    entries.sort(key=lambda item: (item[0][1]+item[0][3])/2)
    height = statistics.median(max(1, box[3]-box[1]) for box, block in entries)
    rows = []
    for box, block in entries:
        center = (box[1]+box[3])/2
        if not rows or abs(center-rows[-1][0]) > height*.45:
            rows.append((center, []))
        rows[-1][1].append((box, block))
    result = []
    for center, entries in rows:
        fragments, right = [], None
        for box, block in sorted(entries, key=lambda entry: entry[0][0]):
            if right is not None and box[0]-right > height*3:
                result.append(fragments)
                fragments = []
            fragments.append((box, block))
            right = max(right or box[2], box[2])
        result.append(fragments)
    return result


class RapidOCRBackend:
    name = 'rapidocr-local'
    is_local = True

    def __init__(self):
        from .models import verify_models
        verify_models()
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        from rapidocr_onnxruntime import RapidOCR
        self._data = files('shiguang_capture.ocr').joinpath('data')
        self._engine = RapidOCR(
            rec_model_path=str(self._data.joinpath('PP-OCRv5_mobile_rec_onnx.onnx')),
            rec_keys_path=str(self._data.joinpath('PP-OCRv5_mobile_rec_onnx-keys.txt')),
            intra_op_num_threads=2, inter_op_num_threads=1, det_limit_type='max')
        self._english = None
        log.info('本地 OCR 引擎已加载')

    def _english_recognizer(self):
        if self._english is None:
            from rapidocr_onnxruntime.ch_ppocr_rec.text_recognize import TextRecognizer
            self._english = TextRecognizer({
                'model_path': str(self._data.joinpath('en_PP-OCRv5_mobile_rec_onnx.onnx')),
                'rec_keys_path': str(self._data.joinpath('en_PP-OCRv5_mobile_rec_onnx-keys.txt')),
                'rec_img_shape': [3,48,320], 'rec_batch_num':6,
                'intra_op_num_threads':2, 'inter_op_num_threads':1,
                'use_cuda':False, 'use_dml':False})
        return self._english

    def recognize(self, image: bytes) -> OCRResult:
        return self._recognize_lines(image, 'ocr')

    def recognize_code(self, image: bytes) -> OCRResult:
        return self._recognize_lines(image, 'code')

    def _recognize_lines(self, image, mode):
        if not image:
            raise ValueError('图像字节流为空')
        started = time.perf_counter()
        detected, _ = self._engine(image)
        if not detected:
            return self._result([], started, mode)
        pixels = self._engine.load_img(image)
        fragments = [{'text': item[1], 'box': item[0], 'confidence':float(item[2])} for item in detected]
        crops, blocks, english = [], [], []
        for row in _rows(fragments):
            box = [round(operation([position[i] for position, block in row]))
                   for i, operation in enumerate((min, min, max, max))]
            left, top, right, bottom = box
            crop = pixels[max(0,top-2):min(pixels.shape[0],bottom+2),
                          max(0,left-2):min(pixels.shape[1],right+2)]
            if crop.size == 0:
                continue
            crops.append(crop)
            english.append(not re.search(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]',
                                         ''.join(block['text'] for position, block in row)))
            blocks.append({'type':'line', 'box':[[left,top],[right,top],[right,bottom],[left,bottom]]})
        # Re-recognize pixels instead of concatenating overlapping fragments or
        # correcting text using a dictionary/LLM.
        for use_english in (False, True):
            indices = [i for i, value in enumerate(english) if value == use_english]
            if not indices:
                continue
            recognizer = self._english_recognizer() if use_english else self._engine.text_rec
            recognized, _ = recognizer([crops[i] for i in indices])
            for index, (text, confidence) in zip(indices, recognized):
                blocks[index].update(text=text, confidence=float(confidence),
                                     model_id='en-PP-OCRv5-mobile' if use_english else 'PP-OCRv5-mobile')
        return self._result(blocks, started, mode)

    def recognize_table(self, image):
        import cv2
        import numpy as np
        started = time.perf_counter()
        boxes, cleaned = detect_grid(image)
        pixels = self._engine.load_img(cleaned)
        cells = [['' for box in row] for row in boxes]
        crops, locations, blocks = [], [], []
        for row_index, row in enumerate(boxes):
            for column, (left,top,right,bottom) in enumerate(row):
                cell = pixels[top+4:bottom-4, left+4:right-4]
                if not cell.size:
                    continue
                gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)
                if int(gray.max())-int(gray.min()) < 25:
                    continue
                _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                occupied = np.flatnonzero(mask.any(axis=1))
                lines = []
                for y in occupied:
                    if not lines or y-lines[-1][-1] > 4:
                        lines.append([])
                    lines[-1].append(int(y))
                for line in lines:
                    ys, xs = np.where(mask[line[0]:line[-1]+1] != 0)
                    if not len(xs):
                        continue
                    x1,x2 = max(0,int(xs.min())-4), min(cell.shape[1],int(xs.max())+5)
                    y1,y2 = max(0,line[0]-4), min(cell.shape[0],line[-1]+5)
                    crops.append(cell[y1:y2,x1:x2])
                    locations.append((row_index,column))
                    x,y = left+4+x1, top+4+y1
                    blocks.append({'type':'line','box':[[x,y],[left+4+x2,y],[left+4+x2,top+4+y2],[x,top+4+y2]]})
        if crops:
            recognized, _ = self._engine.text_rec(crops)
            for block, (row,column), (text,confidence) in zip(blocks,locations,recognized):
                cells[row][column] += ('\n' if cells[row][column] else '')+text
                block.update(text=text,confidence=float(confidence),model_id='PP-OCRv5-mobile')
        result = self._result(blocks, started, 'table')
        result.table = TableData(cells, boxes)
        result.text = '\n'.join('\t'.join(row) for row in cells)
        return result

    def _result(self, blocks, started, mode):
        text = code_from_blocks(blocks) if mode == 'code' else text_from_blocks(blocks)
        return OCRResult(text=text, confidence=statistics.mean(block['confidence'] for block in blocks) if blocks else 0.0,
                         blocks=blocks, engine=self.name, elapsed_ms=round((time.perf_counter()-started)*1000),
                         mode=mode, model_version=MODEL_VERSION)
