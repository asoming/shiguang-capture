"""Bundled OPUS-MT inference, with no downloads or network access at runtime."""
from pathlib import Path
import re
import time

DATA = Path(__file__).with_name('translation_data')


def available():
    return all((DATA/direction/'model/model.bin').is_file() for direction in ('en_zh', 'zh_en'))


class BundledTranslator:
    name = 'opus-mt-local-1.9'
    is_local = True

    def translate(self, text, source, target):
        import ctranslate2
        import sentencepiece
        from .translate import TranslationResult
        started = time.perf_counter()
        directory = DATA/f'{source}_{target}'
        if not (directory/'model/model.bin').is_file():
            raise ValueError('离线翻译支持中文与英文互译。')
        tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(directory/'sentencepiece.model'))
        model = ctranslate2.Translator(str(directory/'model'), device='cpu', compute_type='int8',
                                      inter_threads=1, intra_threads=2)
        translated = []
        for line in text.split('\n'):
            if not line.strip():
                translated.append(line)
                continue
            segments = re.split(r'(?<=[。！？!?])|(?<=\.)\s+', line)
            outputs = []
            for segment in segments:
                tokens = tokenizer.encode(segment, out_type=str)
                if not tokens:
                    continue
                # Explicit chunks ensure no long OCR paragraph is silently truncated.
                chunks = [tokens[offset:offset+256] for offset in range(0, len(tokens), 256)]
                results = model.translate_batch(chunks, beam_size=4, max_decoding_length=512,
                                                max_input_length=0, repetition_penalty=1.05)
                outputs.extend(''.join(result.hypotheses[0]).replace('▁', ' ').strip() for result in results)
            translated.append(('' if target == 'zh' else ' ').join(outputs))
        return TranslationResult(text, '\n'.join(translated), source, target, self.name,
                                 round((time.perf_counter()-started)*1000))
