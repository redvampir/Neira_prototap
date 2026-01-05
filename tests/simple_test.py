"""
SIMPLE TEST: Neira Learning Test
"""

from main import Neira
import json

def simple_test():
    print('=' * 60)
    print('NEIRA LEARNING TEST')
    print('=' * 60)
    
    neira = Neira(verbose=False)
    
    # Test 1: Basic question
    print('\n[TEST 1] Basic Question')
    print('-' * 60)
    q = "Hi! What is your name?"
    print(f'User: {q}')
    response = neira.process(q)
    print(f'Neira: {response[:150]}...')
    
    # Test 2: Memory check
    print('\n[TEST 2] Memory Statistics')
    print('-' * 60)
    with open('neira_memory.json', encoding='utf-8') as f:
        mem = json.load(f)
    print(f'Total records: {len(mem)}')
    print(f'Last record: {mem[-1].get("content", "N/A")[:80]}...')
    
    print('\n[DONE] Test completed!')

if __name__ == '__main__':
    simple_test()
