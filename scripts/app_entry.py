"""app_entry.py — PyInstaller 打包入口。

直接以脚本方式启动应用（等价 python -m shiguang_capture）。
"""
import multiprocessing
multiprocessing.freeze_support()
from shiguang_capture.__main__ import main

if __name__ == "__main__":
    import contextlib
    import os
    import sys
    import traceback

    checks = {'--self-test', '--recording-self-test', '--recording-desktop-test', '--desktop-test'}
    if checks.intersection(sys.argv[1:]):
        # Windowed Windows executables have no console. A failed synthetic test
        # must exit nonzero, rather than opening a traceback dialog and hanging CI.
        with contextlib.ExitStack() as stack:
            log_path = os.environ.get('SHIGUANG_SELF_TEST_LOG')
            if log_path:
                output = stack.enter_context(open(log_path, 'w', encoding='utf-8'))
                stack.enter_context(contextlib.redirect_stdout(output))
                stack.enter_context(contextlib.redirect_stderr(output))
            try:
                result = main()
            except Exception:
                traceback.print_exc()
                result = 1
        raise SystemExit(result)
    raise SystemExit(main())
