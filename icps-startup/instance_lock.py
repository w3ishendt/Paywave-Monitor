from contextlib import contextmanager
from pathlib import Path

import msvcrt

class InstanceAlreadyRunningError(RuntimeError):
    pass

@contextmanager
def single_instance_lock(lock_name):
    lock_path = Path(__file__).resolve().with_name(lock_name)
    lock_file = lock_path.open("a+")

    try:
        lock_file.seek(0)
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise InstanceAlreadyRunningError(lock_name) from exc

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(lock_path))
        lock_file.flush()
        yield
    finally:
        try:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        lock_file.close()