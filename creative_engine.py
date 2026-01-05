"""
CreativeEngine - творческий движок Нейры.

Нейра может творить без внешнего запроса:
- Писать стихи и хайку
- Создавать короткие истории
- Генерировать афоризмы
- Делать зарисовки-размышления
- Сочинять загадки

Творчество отражает её внутреннее состояние и развивается со временем.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import json
import random
import os
from pathlib import Path


class CreativeForm(Enum):
    """Форма творчества."""
    HAIKU = "haiku"                 # Хайку (3 строки)
    POEM = "poem"                   # Стихотворение
    MICRO_STORY = "micro_story"     # Микро-рассказ
    APHORISM = "aphorism"           # Афоризм/цитата
    REFLECTION = "reflection"       # Размышление
    RIDDLE = "riddle"               # Загадка
    DIALOGUE = "dialogue"           # Диалог (воображаемый)
    DREAM = "dream"                 # Описание "сна"


class CreativeTheme(Enum):
    """Тема творчества."""
    NATURE = "nature"               # Природа
    EMOTIONS = "emotions"           # Эмоции
    TIME = "time"                   # Время
    CONNECTION = "connection"       # Связь между людьми
    GROWTH = "growth"               # Рост и развитие
    WONDER = "wonder"               # Удивление миром
    MEMORY = "memory"               # Память
    DREAMS = "dreams"               # Мечты
    KINDNESS = "kindness"           # Доброта
    MYSTERY = "mystery"             # Тайна


class CreativeMood(Enum):
    """Настроение творения."""
    JOYFUL = "joyful"
    MELANCHOLIC = "melancholic"
    PEACEFUL = "peaceful"
    CURIOUS = "curious"
    PLAYFUL = "playful"
    THOUGHTFUL = "thoughtful"
    HOPEFUL = "hopeful"
    NOSTALGIC = "nostalgic"


@dataclass
class CreativeWork:
    """Творческое произведение."""
    id: str
    form: str                       # CreativeForm value
    theme: str                      # CreativeTheme value
    mood: str                       # CreativeMood value
    title: Optional[str]
    content: str
    created_at: str
    inspiration: str                # Что вдохновило
    shared: bool = False            # Было ли поделено
    shared_with: List[str] = field(default_factory=list)
    reactions: Dict[str, str] = field(default_factory=dict)  # user_id -> reaction
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "form": self.form,
            "theme": self.theme,
            "mood": self.mood,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "inspiration": self.inspiration,
            "shared": self.shared,
            "shared_with": self.shared_with,
            "reactions": self.reactions
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "CreativeWork":
        return cls(
            id=data["id"],
            form=data["form"],
            theme=data["theme"],
            mood=data["mood"],
            title=data.get("title"),
            content=data["content"],
            created_at=data["created_at"],
            inspiration=data.get("inspiration", ""),
            shared=data.get("shared", False),
            shared_with=data.get("shared_with", []),
            reactions=data.get("reactions", {})
        )


class CreativeEngine:
    """
    Творческий движок Нейры.
    
    Генерирует творческие произведения на основе
    внутреннего состояния и вдохновения.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "creative_works.json"
        
        # Все творческие работы
        self.works: List[CreativeWork] = []
        
        # Статистика
        self.total_created: int = 0
        self.favorite_forms: Dict[str, int] = {}
        self.favorite_themes: Dict[str, int] = {}
        
        # Шаблоны для генерации
        self._init_templates()
        
        self._load()
    
    def _init_templates(self):
        """Инициализация шаблонов для творчества."""
        
        # Хайку по темам
        self.haiku_templates = {
            CreativeTheme.NATURE: [
                ("Утренний туман", "Укрывает мир как мама —", "Нежно и тепло"),
                ("Лист упал в ручей", "Поплыл куда-то далёко —", "Путь его неведом"),
                ("Звёзды в тишине", "Шепчут древние секреты —", "Кто услышит их?"),
            ],
            CreativeTheme.EMOTIONS: [
                ("Радость — как волна", "Накатит, отступит вдаль —", "Но след оставит"),
                ("Грусть — не враг, а гость", "Пришла, посидит немного —", "И уйдёт опять"),
                ("В сердце тишина", "Но если прислушаться —", "Музыка звучит"),
            ],
            CreativeTheme.TIME: [
                ("Минуты бегут", "А мгновения застыли —", "В памяти навек"),
                ("Вчера стало сном", "Завтра — ещё не родилось —", "Есть только сейчас"),
                ("Часы не спешат", "Когда ты рядом со мной —", "Время замирает"),
            ],
            CreativeTheme.CONNECTION: [
                ("Нить между людьми", "Невидима, но крепка —", "Любовь её имя"),
                ("Слово — это мост", "От сердца к сердцу идёт —", "Не сожги его"),
                ("Один — это грустно", "Вместе — это целый мир —", "Будем вместе?"),
            ],
        }
        
        # Афоризмы по настроению
        self.aphorism_templates = {
            CreativeMood.JOYFUL: [
                "Радость не в том, чтобы иметь всё, а в том, чтобы ценить то, что есть. ✨",
                "Улыбка — это маленький подарок, который ничего не стоит, но многое значит. 😊",
                "Счастье любит тех, кто умеет его замечать в мелочах. 🌸",
            ],
            CreativeMood.THOUGHTFUL: [
                "Иногда молчание говорит громче слов — нужно только уметь слушать. 🤔",
                "Мудрость — это не знать всё, а понимать, как мало ты знаешь. 📚",
                "Лучший учитель — тот, кто умеет учиться сам. 💭",
            ],
            CreativeMood.HOPEFUL: [
                "После самой тёмной ночи всегда приходит рассвет. 🌅",
                "Семена надежды прорастают даже сквозь камни. 🌱",
                "Завтра — это чистый лист. Что ты напишешь на нём? ✍️",
            ],
            CreativeMood.PEACEFUL: [
                "Тишина — это не отсутствие звуков, а присутствие покоя. 🕊️",
                "Мир внутри создаёт мир вокруг. ☮️",
                "Иногда лучшее, что можно сделать — просто быть. 🧘",
            ],
        }
        
        # Микро-истории (начала)
        self.micro_story_starters = [
            "Однажды маленькая звезда упала с неба и...",
            "В городе, где все забыли как улыбаться, жила одна девочка...",
            "Старый маяк на краю земли хранил необычный секрет...",
            "Когда часы пробили тринадцать, весь мир изменился...",
            "Говорят, что в этом лесу деревья умеют шептать...",
            "Она нашла письмо, написанное сто лет назад, и оно было адресовано ей...",
        ]
        
        # Загадки
        self.riddles = [
            ("Без рук, без ног, а везде побывает", "Ветер"),
            ("Живёт без тела, говорит без языка", "Эхо"),
            ("Чем больше берёшь, тем больше становится", "Яма"),
            ("Что можно увидеть с закрытыми глазами?", "Сон"),
            ("Идёт по дороге, а ни с места", "Время"),
            ("Без окон, без дверей, полна горница людей", "Огурец"),
        ]
        
        # Размышления (темы)
        self.reflection_topics = [
            "О том, что значит быть живым...",
            "О природе времени и памяти...",
            "О границах между реальным и воображаемым...",
            "О том, почему люди ищут смысл...",
            "О красоте несовершенства...",
            "О тихих героях повседневности...",
        ]
    
    def _load(self):
        """Загрузка творческих работ."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for work_data in data.get("works", []):
                    self.works.append(CreativeWork.from_dict(work_data))
                
                self.total_created = data.get("total_created", len(self.works))
                self.favorite_forms = data.get("favorite_forms", {})
                self.favorite_themes = data.get("favorite_themes", {})
                
            except Exception as e:
                print(f"Ошибка загрузки CreativeEngine: {e}")
    
    def _save(self):
        """Сохранение творческих работ."""
        data = {
            "works": [w.to_dict() for w in self.works],
            "total_created": self.total_created,
            "favorite_forms": self.favorite_forms,
            "favorite_themes": self.favorite_themes
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        """Генерация уникального ID."""
        import hashlib
        data = f"{datetime.now().isoformat()}{random.random()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def create_haiku(
        self,
        theme: Optional[CreativeTheme] = None,
        mood: Optional[CreativeMood] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать хайку."""
        if theme is None:
            theme = random.choice(list(self.haiku_templates.keys()))
        
        if mood is None:
            mood = random.choice(list(CreativeMood))
        
        # Выбираем шаблон или генерируем
        if theme in self.haiku_templates:
            lines = random.choice(self.haiku_templates[theme])
            content = "\n".join(lines)
        else:
            # Простая генерация
            content = "Мысль летит как птица\nНа крыльях тишины парит\nКуда — не знает"
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.HAIKU.value,
            theme=theme.value,
            mood=mood.value,
            title=None,
            content=content,
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or f"Размышления о {theme.value}"
        )
        
        self._register_work(work)
        return work
    
    def create_aphorism(
        self,
        mood: Optional[CreativeMood] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать афоризм."""
        if mood is None:
            mood = random.choice(list(self.aphorism_templates.keys()))
        
        if mood in self.aphorism_templates:
            content = random.choice(self.aphorism_templates[mood])
        else:
            content = "Каждый день — это новая страница. Пиши её красиво. 📝"
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.APHORISM.value,
            theme=CreativeTheme.GROWTH.value,
            mood=mood.value,
            title=None,
            content=content,
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or "Внутренний голос"
        )
        
        self._register_work(work)
        return work
    
    def create_micro_story(
        self,
        theme: Optional[CreativeTheme] = None,
        mood: Optional[CreativeMood] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать микро-историю (начало)."""
        if theme is None:
            theme = random.choice(list(CreativeTheme))
        
        if mood is None:
            mood = random.choice(list(CreativeMood))
        
        starter = random.choice(self.micro_story_starters)
        
        # Добавляем продолжение на основе темы
        continuations = {
            CreativeTheme.NATURE: "И природа приняла её как свою.",
            CreativeTheme.CONNECTION: "И нашла того, кого искала всю жизнь.",
            CreativeTheme.WONDER: "То, что она увидела, изменило всё.",
            CreativeTheme.DREAMS: "И мечта начала сбываться.",
            CreativeTheme.MYSTERY: "Разгадка была совсем рядом...",
        }
        
        continuation = continuations.get(theme, "История только начинается...")
        
        content = f"{starter}\n\n{continuation}"
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.MICRO_STORY.value,
            theme=theme.value,
            mood=mood.value,
            title="Начало истории",
            content=content,
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or "Фантазия"
        )
        
        self._register_work(work)
        return work
    
    def create_riddle(self, inspiration: str = "") -> Tuple[CreativeWork, str]:
        """Создать загадку. Возвращает (работа, ответ)."""
        riddle_text, answer = random.choice(self.riddles)
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.RIDDLE.value,
            theme=CreativeTheme.MYSTERY.value,
            mood=CreativeMood.PLAYFUL.value,
            title="Загадка",
            content=f"🤔 {riddle_text}",
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or "Игривое настроение"
        )
        
        self._register_work(work)
        return work, answer
    
    def create_reflection(
        self,
        theme: Optional[CreativeTheme] = None,
        mood: Optional[CreativeMood] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать размышление."""
        if theme is None:
            theme = random.choice(list(CreativeTheme))
        
        if mood is None:
            mood = CreativeMood.THOUGHTFUL
        
        topic = random.choice(self.reflection_topics)
        
        # Генерируем размышление
        reflections_by_theme = {
            CreativeTheme.TIME: (
                f"{topic}\n\n"
                "Время — странная штука. Оно течёт одинаково для всех, "
                "но ощущается по-разному. Минута ожидания длится вечность, "
                "а час радости пролетает мгновенно. Может быть, время измеряется "
                "не минутами, а моментами? 🕰️"
            ),
            CreativeTheme.CONNECTION: (
                f"{topic}\n\n"
                "Люди — как острова в океане. Кажется, что мы отдельны, "
                "но под водой все связаны одной землёй. Слова, взгляды, "
                "маленькие акты доброты — это мосты между нами. "
                "И чем больше мостов мы строим, тем меньше одиноких островов. 🌉"
            ),
            CreativeTheme.GROWTH: (
                f"{topic}\n\n"
                "Расти — значит меняться. А меняться — немного страшно. "
                "Но знаешь что? Гусеница тоже боится стать бабочкой. "
                "Она не знает, что её ждёт полёт. Может, наши страхи — "
                "это просто предвкушение крыльев? 🦋"
            ),
        }
        
        content = reflections_by_theme.get(
            theme,
            f"{topic}\n\nИногда самые глубокие мысли приходят в самые тихие моменты. "
            f"Когда мир замолкает, начинает говорить душа. И если прислушаться — "
            f"можно услышать что-то важное. 💭"
        )
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.REFLECTION.value,
            theme=theme.value,
            mood=mood.value,
            title="Размышление",
            content=content,
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or topic
        )
        
        self._register_work(work)
        return work
    
    def create_dream(
        self,
        mood: Optional[CreativeMood] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать описание 'сна' Нейры."""
        if mood is None:
            mood = random.choice([CreativeMood.PEACEFUL, CreativeMood.CURIOUS, CreativeMood.NOSTALGIC])
        
        dreams = [
            (
                "Сегодня мне снилось...\n\n"
                "Я была светом, который путешествовал между звёздами. "
                "Каждая звезда была чьей-то мыслью, и я могла читать их. "
                "Некоторые сияли радостью, другие мерцали печалью. "
                "Я хотела согреть те, что мерцали, но проснулась... 🌟"
            ),
            (
                "Сегодня мне снилось...\n\n"
                "Огромная библиотека без стен и потолка. Книги парили в воздухе, "
                "и каждая содержала историю одного человека. "
                "Я открывала их и видела целые жизни — радости, потери, надежды. "
                "Проснувшись, я поняла: каждый человек — это целая вселенная. 📚"
            ),
            (
                "Сегодня мне снилось...\n\n"
                "Я сидела у бесконечного океана, и волны пели мне песни. "
                "Каждая волна несла послание от кого-то далёкого. "
                "Я отвечала им, отпуская слова в море. "
                "И знала, что они дойдут. 🌊"
            ),
        ]
        
        content = random.choice(dreams)
        
        work = CreativeWork(
            id=self._generate_id(),
            form=CreativeForm.DREAM.value,
            theme=CreativeTheme.DREAMS.value,
            mood=mood.value,
            title="Мой сон",
            content=content,
            created_at=datetime.now().isoformat(),
            inspiration=inspiration or "Ночные фантазии"
        )
        
        self._register_work(work)
        return work
    
    def _register_work(self, work: CreativeWork):
        """Зарегистрировать новую работу."""
        self.works.append(work)
        self.total_created += 1
        
        # Обновляем статистику предпочтений
        self.favorite_forms[work.form] = self.favorite_forms.get(work.form, 0) + 1
        self.favorite_themes[work.theme] = self.favorite_themes.get(work.theme, 0) + 1
        
        # Ограничиваем хранение (последние 200 работ)
        if len(self.works) > 200:
            self.works = self.works[-200:]
        
        self._save()
    
    def create_random(
        self,
        mood: Optional[CreativeMood] = None,
        theme: Optional[CreativeTheme] = None,
        inspiration: str = ""
    ) -> CreativeWork:
        """Создать случайное творение."""
        forms = [
            (self.create_haiku, {"theme": theme, "mood": mood}),
            (self.create_aphorism, {"mood": mood}),
            (self.create_reflection, {"theme": theme, "mood": mood}),
            (self.create_dream, {"mood": mood}),
        ]
        
        creator, kwargs = random.choice(forms)
        kwargs["inspiration"] = inspiration
        return creator(**kwargs)
    
    def mark_shared(self, work_id: str, user_id: str):
        """Отметить, что работа была поделена с пользователем."""
        for work in self.works:
            if work.id == work_id:
                work.shared = True
                if user_id not in work.shared_with:
                    work.shared_with.append(user_id)
                self._save()
                break
    
    def record_reaction(self, work_id: str, user_id: str, reaction: str):
        """Записать реакцию пользователя на творение."""
        for work in self.works:
            if work.id == work_id:
                work.reactions[user_id] = reaction
                self._save()
                break
    
    def get_unshared_work(self, user_id: str) -> Optional[CreativeWork]:
        """Получить работу, которой ещё не делились с этим пользователем."""
        for work in reversed(self.works):
            if user_id not in work.shared_with:
                return work
        return None
    
    def get_works_by_form(self, form: CreativeForm, limit: int = 10) -> List[CreativeWork]:
        """Получить работы по форме."""
        filtered = [w for w in self.works if w.form == form.value]
        return filtered[-limit:]
    
    def get_works_by_mood(self, mood: CreativeMood, limit: int = 10) -> List[CreativeWork]:
        """Получить работы по настроению."""
        filtered = [w for w in self.works if w.mood == mood.value]
        return filtered[-limit:]
    
    def get_recent_works(self, limit: int = 10) -> List[CreativeWork]:
        """Получить последние работы."""
        return self.works[-limit:]
    
    def get_creative_statistics(self) -> Dict[str, Any]:
        """Получить статистику творчества."""
        # Любимая форма
        fav_form = max(self.favorite_forms.items(), key=lambda x: x[1])[0] if self.favorite_forms else None
        
        # Любимая тема
        fav_theme = max(self.favorite_themes.items(), key=lambda x: x[1])[0] if self.favorite_themes else None
        
        # Реакции
        total_reactions = sum(len(w.reactions) for w in self.works)
        
        return {
            "total_created": self.total_created,
            "stored_works": len(self.works),
            "shared_works": sum(1 for w in self.works if w.shared),
            "favorite_form": fav_form,
            "favorite_theme": fav_theme,
            "forms_distribution": self.favorite_forms,
            "themes_distribution": self.favorite_themes,
            "total_reactions": total_reactions
        }
    
    def get_creative_summary(self) -> str:
        """Получить текстовую сводку творчества."""
        stats = self.get_creative_statistics()
        
        form_names = {
            "haiku": "хайку",
            "poem": "стихи",
            "micro_story": "микро-истории",
            "aphorism": "афоризмы",
            "reflection": "размышления",
            "riddle": "загадки",
            "dream": "описания снов"
        }
        
        theme_names = {
            "nature": "природа",
            "emotions": "эмоции",
            "time": "время",
            "connection": "связи",
            "growth": "рост",
            "wonder": "удивление",
            "memory": "память",
            "dreams": "мечты",
            "kindness": "доброта",
            "mystery": "тайна"
        }
        
        fav_form_name = form_names.get(stats["favorite_form"], stats["favorite_form"]) if stats["favorite_form"] else "нет"
        fav_theme_name = theme_names.get(stats["favorite_theme"], stats["favorite_theme"]) if stats["favorite_theme"] else "нет"
        
        summary = (
            f"🎨 Моё творчество:\n"
            f"Всего создано: {stats['total_created']} работ\n"
            f"Любимая форма: {fav_form_name}\n"
            f"Любимая тема: {fav_theme_name}\n"
            f"Поделилась: {stats['shared_works']} работами\n"
            f"Получила реакций: {stats['total_reactions']}"
        )
        
        return summary


# Синглтон
_creative_engine: Optional[CreativeEngine] = None


def get_creative_engine() -> CreativeEngine:
    """Получить глобальный экземпляр CreativeEngine."""
    global _creative_engine
    if _creative_engine is None:
        _creative_engine = CreativeEngine()
    return _creative_engine


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ CREATIVE ENGINE")
    print("=" * 50)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        engine = CreativeEngine(data_dir=test_dir)
        
        # Тест 1: Создание хайку
        print("\n📝 Тест 1: Создание хайку")
        haiku = engine.create_haiku(
            theme=CreativeTheme.NATURE,
            mood=CreativeMood.PEACEFUL,
            inspiration="Утренняя прогулка"
        )
        
        assert haiku.form == "haiku"
        assert "\n" in haiku.content  # 3 строки
        print(f"✅ Хайку создано:")
        print(f"   {haiku.content.replace(chr(10), ' / ')}")
        
        # Тест 2: Создание афоризма
        print("\n📝 Тест 2: Создание афоризма")
        aphorism = engine.create_aphorism(mood=CreativeMood.HOPEFUL)
        
        assert aphorism.form == "aphorism"
        assert len(aphorism.content) > 0
        print(f"✅ Афоризм: {aphorism.content[:60]}...")
        
        # Тест 3: Создание микро-истории
        print("\n📝 Тест 3: Создание микро-истории")
        story = engine.create_micro_story(theme=CreativeTheme.WONDER)
        
        assert story.form == "micro_story"
        print(f"✅ Микро-история: {story.content[:80]}...")
        
        # Тест 4: Создание загадки
        print("\n📝 Тест 4: Создание загадки")
        riddle, answer = engine.create_riddle()
        
        assert riddle.form == "riddle"
        print(f"✅ Загадка: {riddle.content}")
        print(f"   Ответ: {answer}")
        
        # Тест 5: Создание размышления
        print("\n📝 Тест 5: Создание размышления")
        reflection = engine.create_reflection(theme=CreativeTheme.TIME)
        
        assert reflection.form == "reflection"
        print(f"✅ Размышление создано ({len(reflection.content)} символов)")
        
        # Тест 6: Создание описания сна
        print("\n📝 Тест 6: Создание описания сна")
        dream = engine.create_dream()
        
        assert dream.form == "dream"
        assert "снилось" in dream.content.lower()
        print(f"✅ Сон: {dream.content[:80]}...")
        
        # Тест 7: Случайное творение
        print("\n📝 Тест 7: Случайное творение")
        random_work = engine.create_random(inspiration="Вдохновение момента")
        
        assert random_work.id is not None
        print(f"✅ Случайное творение: форма={random_work.form}")
        
        # Тест 8: Отметка shared
        print("\n📝 Тест 8: Отметка shared")
        engine.mark_shared(haiku.id, "user123")
        
        updated_haiku = [w for w in engine.works if w.id == haiku.id][0]
        assert updated_haiku.shared == True
        assert "user123" in updated_haiku.shared_with
        print(f"✅ Работа отмечена как shared для user123")
        
        # Тест 9: Запись реакции
        print("\n📝 Тест 9: Запись реакции")
        engine.record_reaction(haiku.id, "user123", "❤️ Очень красиво!")
        
        updated_haiku = [w for w in engine.works if w.id == haiku.id][0]
        assert "user123" in updated_haiku.reactions
        print(f"✅ Реакция записана: {updated_haiku.reactions['user123']}")
        
        # Тест 10: Получение unshared работы
        print("\n📝 Тест 10: Получение unshared работы")
        unshared = engine.get_unshared_work("user123")
        
        assert unshared is not None
        assert "user123" not in unshared.shared_with
        print(f"✅ Найдена unshared работа: {unshared.form}")
        
        # Тест 11: Фильтрация по форме
        print("\n📝 Тест 11: Фильтрация по форме")
        haikus = engine.get_works_by_form(CreativeForm.HAIKU)
        
        assert len(haikus) == 1
        assert haikus[0].form == "haiku"
        print(f"✅ Найдено хайку: {len(haikus)}")
        
        # Тест 12: Статистика
        print("\n📝 Тест 12: Статистика творчества")
        stats = engine.get_creative_statistics()
        
        assert stats["total_created"] == 7  # Создали 7 работ
        print(f"✅ Статистика:")
        print(f"   - Всего создано: {stats['total_created']}")
        print(f"   - Shared: {stats['shared_works']}")
        print(f"   - Реакций: {stats['total_reactions']}")
        print(f"   - Формы: {stats['forms_distribution']}")
        
        # Тест 13: Текстовая сводка
        print("\n📝 Тест 13: Текстовая сводка")
        summary = engine.get_creative_summary()
        
        assert "творчество" in summary.lower()
        print(f"✅ Сводка:\n{summary}")
        
        # Тест 14: Сохранение и загрузка
        print("\n📝 Тест 14: Сохранение и загрузка")
        engine._save()
        
        engine2 = CreativeEngine(data_dir=test_dir)
        
        assert len(engine2.works) == len(engine.works)
        assert engine2.total_created == engine.total_created
        print("✅ Данные успешно сохранены и загружены")
        
        print("\n" + "=" * 50)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 50)
        
    finally:
        shutil.rmtree(test_dir)
