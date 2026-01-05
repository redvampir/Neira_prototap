import os
os.environ['NEIRA_LOCAL_EMBEDDINGS'] = 'true'

from response_engine import get_response_engine

engine = get_response_engine()

q = 'Привет Нейра. Как твоя система создания органов?'
resp, src = engine.try_respond_autonomous(q, {'user_name':'Pavel'})
print('QUERY:', q)
print('RESPONSE:', resp)
print('SOURCE:', src)

q2 = 'Поясни подробно, как работает pipeline создания органов и какие проверки выполняет OrganGuardian?'
resp2, src2 = engine.try_respond_autonomous(q2, {'user_name':'Pavel'})
print('\nQUERY2:', q2)
print('RESPONSE2:', resp2)
print('SOURCE2:', src2)
