"""Check real bundled models through the same cancellable process as the UI."""
import json
import threading
from .config import AppConfig
from .ocr.worker import RecognitionRunner
from .offline_translation import available


def run():
    assert available(), 'Bundled translation models missing'
    runner = RecognitionRunner()
    evidence = []
    try:
        cases = [('The meeting starts at nine tomorrow morning.', '明天', '会议'),
                 ('请先保存文件，然后关闭窗口。', 'save', 'window')]
        for source, first, second in cases:
            result, translation = runner.run(source, 'translate_text', AppConfig(), threading.Event())
            assert result.text == source
            assert not translation.degraded
            assert translation.engine == 'opus-mt-local-1.9'
            output = translation.target_text.lower()
            assert first in output and second in output, output
            assert '▁' not in output
            evidence.append({'source': source, 'target': translation.target_text,
                             'engine': translation.engine, 'elapsed_ms': translation.elapsed_ms})
        print(json.dumps({'translation_self_test': 'PASS', 'cases': evidence}, ensure_ascii=False))
        return 0
    finally:
        runner.close()
