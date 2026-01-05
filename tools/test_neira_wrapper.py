import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.neira_wrapper import NeiraWrapper


async def main():
    w = NeiraWrapper(verbose=False)
    print('NeiraWrapper created')
    res = await w.process('Привет, как дела?')
    print('RESPONSE:\n', res)


if __name__ == '__main__':
    asyncio.run(main())
