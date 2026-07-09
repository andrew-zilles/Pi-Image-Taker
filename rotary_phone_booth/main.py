import logging
import signal

from rotary_phone.config import Config
from rotary_phone.controller import PhoneController


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config.load()
    controller = PhoneController(config)

    signal.signal(signal.SIGTERM, lambda *_: None)
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()


if __name__ == "__main__":
    main()
