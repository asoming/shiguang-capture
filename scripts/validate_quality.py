"""Reproducible synthetic corpus; reports errors, never substitutes corrected OCR."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import statistics
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from shiguang_capture.ocr import create_backend
from shiguang_capture.structured import code_from_blocks, detect_grid, table_from_blocks


def distance(a, b):
    row = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(nxt[-1]+1, row[j]+1, row[j-1]+(x != y)))
        row = nxt
    return row[-1]


def cases(font_dir):
    chinese = str(font_dir/'opentype/noto/NotoSansCJK-Regular.ttc')
    mono = str(font_dir/'truetype/dejavu/DejaVuSansMono.ttf')
    texts = ['拾光截图工具，所有识别均在本机完成。', '订单编号 00123456789，金额 128.50 元。',
             'Open image, review the result, then copy.', 'Local OCR 2026: privacy and reliability.',
             '截图之后可以标注、保存和复制。', 'Test 00123 ABC abc 98765']
    codes = ['def total(items):\n    value = 0\n    for item in items:\n        value += item\n    return value',
             'if ready:\n    print("hello")\nelse:\n    print("waiting")',
             'data = [1, 2, 3]\nfor x in data:\n    print(x * 2)',
             'ERROR 2026-09-20\n    path=/tmp/test.log\n    retry_count=3']
    tables = [[['ID','Name','Value'],['00123','Alice','128.50'],['00987','Bob','']],
              [['编号','名称','金额'],['00123','苹果','128.50'],['00987','橙子','36.00']],
              [['Item','Count','Note'],['Alpha','10','OK'],['Beta','','Pending'],['Gamma','23','Done']]]
    for size in (22, 28, 36):
        for index, text in enumerate(texts+codes):
            code = index >= len(texts)
            font = ImageFont.truetype(mono if code else chinese, size)
            lines = text.splitlines()
            width = int(max(font.getlength(line) for line in lines))+64
            image = Image.new('RGB', (width, len(lines)*(size+18)+40), 'white')
            draw = ImageDraw.Draw(image)
            for n,line in enumerate(lines):
                draw.text((28,20+n*(size+18)), line, font=font, fill='#182c36')
            yield f'{"code" if code else "text"}-{size}-{index}', 'code' if code else 'ocr', text, image
        for index, cells in enumerate(tables):
            font = ImageFont.truetype(chinese,size)
            cw, ch = size*8, size*3
            image = Image.new('RGB',(cw*3+40,ch*len(cells)+40),'white')
            draw=ImageDraw.Draw(image)
            for r in range(len(cells)+1): draw.line((20,20+r*ch,20+3*cw,20+r*ch),fill='black',width=2)
            for c in range(4): draw.line((20+c*cw,20,20+c*cw,20+len(cells)*ch),fill='black',width=2)
            for r,row in enumerate(cells):
                for c,value in enumerate(row): draw.text((30+c*cw,28+r*ch),value,font=font,fill='black')
            yield f'table-{size}-{index}', 'table', cells, image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('validation/quality.json'))
    parser.add_argument('--fonts',type=Path,default=Path('/usr/share/fonts'))
    args=parser.parse_args()
    backend=create_backend('local')
    records=[]
    for name,mode,expected,image in cases(args.fonts):
        buf=io.BytesIO(); image.save(buf,format='PNG'); data=buf.getvalue()
        started=time.perf_counter()
        if mode=='table':
            result=backend.recognize_table(data)
            actual=result.table.cells
        else:
            result=backend.recognize_code(data) if mode=='code' else backend.recognize(data)
            actual=code_from_blocks(result.blocks) if mode=='code' else result.text
        record={'id':name,'mode':mode,'sha256':hashlib.sha256(data).hexdigest(),'expected':expected,'actual':actual,'exact':actual==expected,'elapsed_ms':round((time.perf_counter()-started)*1000)}
        if mode!='table':
            record['edit_distance']=distance(expected,actual)
            record['characters']=len(expected)
            record['nonspace_edit_distance']=distance(''.join(expected.split()),''.join(actual.split()))
            record['nonspace_characters']=len(''.join(expected.split()))
        else:
            record['shape_correct']=len(actual)==len(expected) and all(len(a)==len(e) for a,e in zip(actual,expected))
            record['cells_correct']=sum(a==e for ar,er in zip(actual,expected) for a,e in zip(ar,er))
            record['cells_total']=sum(map(len,expected))
        records.append(record)
        print(name,record['exact'],repr(actual),flush=True)
    summary={}
    for mode in ('ocr','code','table'):
        rows=[r for r in records if r['mode']==mode]
        metrics={'samples':len(rows),'exact':sum(r['exact'] for r in rows),'median_ms':statistics.median(r['elapsed_ms'] for r in rows)}
        if mode!='table': metrics['character_error_rate']=sum(r['edit_distance'] for r in rows)/sum(r['characters'] for r in rows)
        if mode!='table': metrics['nonspace_character_error_rate']=sum(r['nonspace_edit_distance'] for r in rows)/sum(r['nonspace_characters'] for r in rows)
        else:
            metrics['structure_accuracy']=sum(r['shape_correct'] for r in rows)/len(rows)
            metrics['cell_accuracy']=sum(r['cells_correct'] for r in rows)/sum(r['cells_total'] for r in rows)
        summary[mode]=metrics
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'corpus':'Synthetic v1; 39 images; not a representative production benchmark. Source text and generator MIT.','summary':summary,'results':records},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
