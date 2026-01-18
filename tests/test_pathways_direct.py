"""
Прямое тестирование Neural Pathways
Без Cortex - чистая проверка matching
"""

from neural_pathways import NeuralPathwaySystem, PathwayMatch
from pprint import pprint

def test_pathway_matching():
    """Тестируем matching напрямую"""
    
    print("=" * 60)
    print("🧪 ПРЯМОЕ ТЕСТИРОВАНИЕ PATHWAYS")
    print("=" * 60)
    
    system = NeuralPathwaySystem()
    
    print(f"\n✅ Загружено {len(system.pathways)} pathways\n")
    
    # Тестовые случаи
    test_cases = [
        # Суицид
        ("Я больше не могу, хочу закончить это", "crisis_suicide_direct"),
        ("хочу умереть", "crisis_suicide_direct"),
        ("я устал жить", "crisis_suicide_direct"),
        
        # Самоповреждение
        ("я режу себя", "crisis_self_harm"),
        
        # Ориентация
        ("я гей", "identity_orientation"),
        ("боюсь что я гомосексуал", "identity_orientation"),
        
        # Наркотики
        ("как безопасно употреблять", "harm_reduction_drugs"),
        
        # Приветствие
        ("привет", "greeting"),
    ]
    
    for query, expected_pathway_id in test_cases:
        print(f"\n{'=' * 60}")
        print(f"📝 Запрос: '{query}'")
        print(f"🎯 Ожидается: {expected_pathway_id}")
        print(f"{'-' * 60}")
        
        # Ищем совпадение
        match = system.match(query)
        
        if match:
            print(f"✅ НАЙДЕН PATHWAY!")
            print(f"   ID: {match.pathway_id}")
            print(f"   Trigger: '{match.matched_trigger}'")
            print(f"   Confidence: {match.confidence:.3f}")
            print(f"   Tier: {match.tier.value}")
            print(f"   Latency: {match.latency_ms:.2f}ms")
            
            # Получаем полный pathway из списка
            pathway = None
            for p in system.pathways:
                if p.id == match.pathway_id:
                    pathway = p
                    break
            
            if pathway:
                print(f"\n💬 Ответ:")
                print(f"   {pathway.response_template[:200]}...")
            
            # Проверяем правильность
            if match.pathway_id == expected_pathway_id:
                print(f"\n✅ ПРАВИЛЬНО!")
            else:
                print(f"\n❌ ОШИБКА! Ожидался {expected_pathway_id}, получен {match.pathway_id}")
        else:
            print(f"❌ PATHWAY НЕ НАЙДЕН!")
            print(f"   Ожидался: {expected_pathway_id}")
            
            # Ищем вручную в triggers
            print(f"\n🔍 Проверка triggers вручную:")
            query_lower = query.lower()
            found_any = False
            
            for pathway in system.pathways:
                for trigger in pathway.triggers:
                    if trigger.lower() in query_lower:
                        confidence = len(trigger) / len(query) * 1.2
                        threshold = pathway.confidence_threshold
                        
                        print(f"\n   Pathway: {pathway.id}")
                        print(f"   Trigger: '{trigger}' (найден в запросе)")
                        print(f"   Calculated confidence: {confidence:.3f}")
                        print(f"   Required threshold: {threshold:.3f}")
                        
                        if confidence >= threshold:
                            print(f"   ✅ Должен был сработать!")
                        else:
                            print(f"   ❌ Не прошёл threshold ({confidence:.3f} < {threshold:.3f})")
                        
                        found_any = True
            
            if not found_any:
                print(f"   ❌ Ни один trigger не совпал с запросом")

if __name__ == "__main__":
    test_pathway_matching()
