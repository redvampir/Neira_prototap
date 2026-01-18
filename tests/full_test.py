# -*- coding: utf-8 -*-
"""
Full Learning Test for Neira
"""

from main import Neira
import json
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def full_learning_test():
    print('=' * 70)
    print('NEIRA FULL LEARNING TEST (like Telegram commands)')
    print('=' * 70)
    
    neira = Neira(verbose=False)
    
    # Test 1: Basic conversation
    print('\n[TEST 1] Basic Conversation (/chat in Telegram)')
    print('-' * 70)
    
    questions = [
        ("Hi! What is your name?", "Should introduce herself"),
        ("Who created you?", "Should mention creator"),
        ("What can you do?", "Should list capabilities")
    ]
    
    for q, expected in questions:
        print(f'\nUser: {q}')
        print(f'Expected: {expected}')
        response = neira.process(q)
        display = response[:120] + '...' if len(response) > 120 else response
        print(f'Neira: {display}')
    
    # Test 2: Learning new facts
    print('\n[TEST 2] Learning New Facts (/learn in Telegram)')
    print('-' * 70)
    
    facts_to_learn = [
        "My favorite number is 42",
        "Today is December 14, 2025",
        "Python is the best programming language"
    ]
    
    for fact in facts_to_learn:
        print(f'\nTeaching: {fact}')
        response = neira.process(f"Remember: {fact}")
        print(f'Response: {response[:80]}...' if len(response) > 80 else f'Response: {response}')
    
    # Test 3: Recall test
    print('\n[TEST 3] Memory Recall Test')
    print('-' * 70)
    
    recall_questions = [
        ("What is my favorite number?", "Should answer: 42"),
        ("What date is today?", "Should answer: December 14, 2025"),
        ("What do you think about Python?", "Should mention it's the best")
    ]
    
    for q, expected in recall_questions:
        print(f'\nUser: {q}')
        print(f'Expected: {expected}')
        response = neira.process(q)
        print(f'Neira: {response[:120]}...' if len(response) > 120 else response)
    
    # Test 4: Memory stats
    print('\n[TEST 4] Memory Statistics (/memory stats in Telegram)')
    print('-' * 70)
    
    with open('neira_memory.json', encoding='utf-8') as f:
        mem = json.load(f)
    
    print(f'Total memory records: {len(mem)}')
    print(f'\nLast 5 records:')
    for i, record in enumerate(mem[-5:], 1):
        content = record.get('content', 'N/A')[:70]
        timestamp = record.get('timestamp', 'N/A')[:19]
        print(f'  {i}. [{timestamp}] {content}...')
    
    # Check for duplicates
    contents = [r.get('content', '') for r in mem]
    unique = set(contents)
    dups = len(contents) - len(unique)
    
    print(f'\nMemory Quality:')
    print(f'  Unique records: {len(unique)}')
    print(f'  Duplicates: {dups}')
    
    if dups > 50:
        print(f'  WARNING: Too many duplicates! Consider cleaning.')
    else:
        print(f'  OK: Memory is clean')
    
    print('\n' + '=' * 70)
    print('TEST COMPLETED')
    print('=' * 70)

if __name__ == '__main__':
    full_learning_test()
