from pathlib import Path


def recover_worker(connection, source, target):
    from .encoder import recover_recording
    try:
        path = recover_recording(Path(source), Path(target))
        connection.send({'type': 'finished', 'path': str(path)})
    except Exception as exc:
        connection.send({'type': 'error', 'message': str(exc), 'recovery': source})
    finally:
        connection.close()
