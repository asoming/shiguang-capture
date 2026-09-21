"""Bounded, on-demand thumbnails from native screen/window capture.

The UI requests one frame at a time. Preview capture and conversion run in a
separate process, never queue full-resolution frames or touch recording files.
"""
import time


def preview_worker(connection, screen_name, region=None, window_title=None):
    from PySide6.QtCore import QRect, QTimer, Qt
    from PySide6.QtGui import QGuiApplication, QImage
    from PySide6.QtMultimedia import QMediaCaptureSession, QScreenCapture, QWindowCapture, QVideoSink, QVideoFrame
    from .frames import rgb_image

    app = QGuiApplication([])
    capture = None
    try:
        screen = next((s for s in app.screens() if s.name() == screen_name), None)
        if not screen and not window_title:
            raise ValueError('所选屏幕已断开，请重新选择')
        if region and (not screen or not screen.geometry().contains(QRect(*region))):
            raise ValueError('预览区域需要位于同一屏幕内')
        session, sink = QMediaCaptureSession(), QVideoSink()
        if window_title:
            windows = [w for w in QWindowCapture.capturableWindows()
                       if w.isValid() and w.description() == window_title]
            if len(windows) != 1:
                raise ValueError('窗口已关闭或标题已变化，请重新选择')
            capture = QWindowCapture()
            capture.setWindow(windows[0])
            session.setWindowCapture(capture)
        else:
            capture = QScreenCapture()
            capture.setScreen(screen)
            session.setScreenCapture(capture)
        session.setVideoSink(sink)
        latest = QVideoFrame()
        last_frame_at = time.monotonic()
        requested = False
        deadline = time.monotonic() + 12

        def receive_frame(frame):
            nonlocal latest, last_frame_at
            if frame.isValid():
                latest = QVideoFrame(frame)
                last_frame_at = time.monotonic()

        def fail(message):
            try:
                connection.send({'type': 'error', 'message': message})
            except (EOFError, BrokenPipeError, OSError):
                pass
            app.quit()

        def tick():
            nonlocal requested, latest
            try:
                while connection.poll():
                    command = connection.recv()
                    if command == 'stop':
                        app.quit()
                        return
                    requested = True
                if not requested:
                    return
                if not latest.isValid():
                    if time.monotonic() > deadline:
                        fail('预览未收到画面，请检查屏幕录制权限或重新选择范围')
                    return
                if time.monotonic() - last_frame_at > 8:
                    fail('画面已中断，请检查窗口是否最小化或重新选择范围')
                    return
                crop = None
                if region:
                    geometry = screen.geometry()
                    sx, sy = latest.width()/geometry.width(), latest.height()/geometry.height()
                    x, y, width, height = region
                    crop = QRect(round((x-geometry.x())*sx), round((y-geometry.y())*sy),
                                 round(width*sx), round(height*sy))
                image = rgb_image(latest, crop)
                if image.isNull():
                    raise ValueError('无法读取预览画面')
                size = (image.width(), image.height())
                image = image.scaled(800, 450, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.FastTransformation)
                image = image.convertToFormat(QImage.Format.Format_RGB888)
                connection.send({'type': 'frame', 'width': image.width(), 'height': image.height(),
                                 'stride': image.bytesPerLine(), 'pixels': bytes(image.constBits()),
                                 'source_size': size})
                requested = False
            except (EOFError, BrokenPipeError, OSError):
                app.quit()
            except Exception as exc:
                fail(str(exc))

        sink.videoFrameChanged.connect(receive_frame)
        capture.errorOccurred.connect(lambda error, text: fail('预览不可用：'+text))
        if screen:
            app.screenRemoved.connect(lambda removed: fail('所选屏幕已断开') if removed == screen else None)
            screen.geometryChanged.connect(lambda *_: fail('屏幕尺寸已变化，请重新选择范围'))
        timer = QTimer()
        timer.setInterval(30)
        timer.timeout.connect(tick)
        timer.start()
        capture.start()
        app.exec()
    except Exception as exc:
        try:
            connection.send({'type': 'error', 'message': str(exc)})
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        if capture:
            capture.stop()
        connection.close()
