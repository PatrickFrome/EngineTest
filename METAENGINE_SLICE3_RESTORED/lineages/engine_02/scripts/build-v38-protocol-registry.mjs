import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("..", import.meta.url)));

const C = (id, prompt, options = {}) => ({
  id,
  prompt,
  required: options.required ?? true,
  evidence_required: options.evidence ?? false,
  human_judgment: options.human ?? false,
  on_no: options.onNo ?? "SUSPEND",
});

const P = (id, title, group, status, automation, locators, checks, value, activation = "EXPLICIT") => ({
  id,
  version: "1.0",
  title_ru: title,
  group,
  status,
  automation,
  activation,
  source_locators: locators,
  value,
  checks,
});

const protocols = [
  P("V38-PRECODE-SCENE", "P−1: сцена до кода", "CORE", "ACTIVE_CORE", "MIXED", ["#L253-L292", "#L25677-L25689"], [
    C("SCENE_PLAIN", "Сцена описана обычным языком до проектных кодов?", { evidence: true, onNo: "FAIL" }),
    C("VORGRIFF_EXPLICIT", "Зафиксированы вопрос, ожидание и принцип отбора исследователя?", { evidence: true }),
    C("ALTERNATIVES_VISIBLE", "Отмечены доступные участникам альтернативы без их преждевременной оценки?", { human: true }),
  ], "Снижает самоподтверждение и кодовое производство феномена.", "ALWAYS"),

  P("V38-SOURCE-AUDIT", "Источниковый и хронологический шлюз", "CORE", "ACTIVE_CORE", "MIXED", ["#L1300-L1405", "#L25475-L25488", "#L20014-L20093"], [
    C("SOURCE_IDENTIFIED", "Указаны источник, редакция, язык, дата, жанр и точный локатор?", { evidence: true, onNo: "FAIL" }),
    C("TEXT_ORDERS", "Разведены дата создания, публикации, место в собрании и поздняя композиция?", { evidence: true }),
    C("GENRE_WEIGHT", "Доказательный вес соотнесён с жанром и редакторским вмешательством?", { human: true }),
    C("SOURCE_PROJECT_SEPARATED", "Цитата, реконструкция, перевод и проектный вывод разведены?", { evidence: true, onNo: "FAIL" }),
  ], "Предотвращает анахронизм, ложную атрибуцию и одинаковый вес неодинаковых свидетельств.", "ALWAYS"),

  P("V38-ONTOLOGY-GATE", "Фундаментально-онтологический шлюз", "CORE", "ACTIVE_CORE", "MIXED", ["#L339-L362", "#L25454-L25474", "#L25709-L25720"], [
    C("TARGET_MODE", "Названы исследуемое сущее, способ бытия или регион?", { evidence: true, onNo: "FAIL" }),
    C("NO_REIFICATION", "Бытие не превращено в сущую причину, процесс, отношение или систему?", { human: true }),
    C("ACCESS_EXISTENCE_SPLIT", "Условие доступа не перенесено на существование без отдельного моста?", { human: true, onNo: "FAIL" }),
    C("DEPENDENCY_PROFILE", "Разведены происхождение, поддержание, тождество и доступ?", { evidence: true }),
    C("RIVALS_PRESENT", "Представлены альтернативные онтологии того же explanandum и масштаба?", { evidence: true }),
  ], "Защищает онтологический уровень от категориальных скачков.", "ALWAYS"),

  P("V38-CLAIM-DISCIPLINE", "Режимы утверждения и доказательная дисциплина", "CORE", "ACTIVE_CORE", "DETERMINISTIC", ["#L169-L182", "#L25520-L25543", "#L673-L701"], [
    C("ORIGIN_MARKED", "Отмечено происхождение тезиса: текст, язык, сцена, данные, норма или реконструкция?", { evidence: true, onNo: "FAIL" }),
    C("JUSTIFICATION_MODE", "Отмечен режим обоснования: описание, вывод, абдукция, сравнение, контрфактический тест или принцип?", { onNo: "FAIL" }),
    C("SCALE_MARKED", "Явно указан масштаб допустимого вывода?", { onNo: "FAIL" }),
    C("REVISION_TRIGGER", "Задано условие понижения, приостановки или удаления?", { evidence: true, onNo: "FAIL" }),
  ], "Не позволяет переносить силу между текстовым, феноменальным, эмпирическим и нормативным каналами.", "ALWAYS"),

  P("V38-D2.8-CORE", "Обязательное ядро D2.8-PROJ", "CORE", "ACTIVE_CORE", "MIXED", ["#L25669-L25735"], [
    C("P_MINUS_1", "Выполнена независимая сцена P−1?", { evidence: true, onNo: "FAIL" }),
    C("LOCAL_RECONSTRUCTION", "Корпус и переход A→P→B реконструированы локально?", { evidence: true, onNo: "FAIL" }),
    C("PROBLEMGENESIS", "История слова, функции и вопроса разведены; для сильной генеалогии дана контргенеалогия?", { human: true }),
    C("DECONFLATION", "Феноменальное, семантическое, эпистемическое, прагматическое, временное и онтологическое разведены?", { human: true }),
    C("META_RESIDUE", "Зафиксированы R1/R2/R3 и условие повторного запуска?", { evidence: true }),
  ], "Минимальный исполнимый каркас действующего метода.", "ALWAYS"),

  P("V38-GATE-12", "GATE-12: шлюз сильного перехода", "CORE", "ACTIVE_CORE", "MIXED", ["#L25736-L25776"], [
    C("THESIS_SCOPE", "Точный тезис и масштаб зафиксированы?", { evidence: true, onNo: "FAIL" }),
    C("BRIDGE_TYPED", "Переход A→P→B типизирован и мост имеет свидетельство?", { evidence: true, onNo: "FAIL" }),
    C("LEVELS_SEPARATED", "Доступ, описание, интерпретация и онтологический вывод разведены?", { human: true, onNo: "FAIL" }),
    C("RIVAL_STEELMAN", "Сильнейшая альтернатива работает на том же explanandum, уровне и масштабе?", { evidence: true, human: true }),
    C("K_AND_DELTA", "Минимальное ядро K и различающий остаток ΔO указаны отдельно?", { evidence: true }),
    C("NEGATIVE_TEST", "Задан выполнимый тест, способный понизить или удалить вывод?", { evidence: true, onNo: "FAIL" }),
  ], "Концентрирует повторяющиеся двенадцатишаговые шлюзы в одном действующем стандарте.", "ON_STRONG_TRANSITION"),

  P("V38-META-DESTRUCTION", "Метадеструкция применённого протокола", "CORE", "ACTIVE_CORE", "HUMAN_REVIEW", ["#L25633-L25668", "#L27347-L27383"], [
    C("PROTOCOL_VORGRIFF", "Предпочтения и Vorgriff самого протокола названы?", { evidence: true, human: true }),
    C("CODE_INFLATION", "Проверено, не заменяет ли выполнение рубрик исследовательское суждение?", { human: true }),
    C("INDEPENDENT_REDESCRIPTION", "Материал повторно описан без словаря результата?", { evidence: true, human: true }),
    C("SELF_CONFIRMATION", "Контргипотеза допускает исчезновение собственного словаря проекта?", { evidence: true, human: true }),
  ], "Удерживает автоматизацию от превращения в самоподтверждающийся ритуал.", "AT_FINALIZATION"),

  P("V38-STOP-KILL", "Правило остановки, suspension point и KILL", "CORE", "ACTIVE_CORE", "DETERMINISTIC", ["#L183-L196", "#L25791-L25806", "#L27474-L27524"], [
    C("STOP_CONDITIONS", "Мотивирующий феномен, rivals, K/ΔO, масштаб и отрицательный тест зафиксированы?", { evidence: true }),
    C("KILL_PREDECLARED", "Условия отказа объявлены до просмотра основного результата?", { evidence: true, onNo: "FAIL" }),
    C("SUSPENSION_EXPLICIT", "При недоопределённости выбран SUSPEND, а не сильный вывод?", { onNo: "FAIL" }),
    C("NO_RETROFIT", "Порог и kill-правила не понижены задним числом?", { evidence: true, onNo: "FAIL" }),
  ], "Делает отрицательный результат допустимым и блокирует бесконечное расширение.", "ALWAYS"),

  P("V38-POWER-GATE", "POWER-GATE", "GATE", "ACTIVE_TRIGGERED", "MIXED", ["#L638-L672", "#L19836-L19910"], [
    C("OPTION_SET_OWNER", "Установлено, кто формирует набор, видимость и цену альтернатив?", { evidence: true, human: true }),
    C("REFUSAL_COST", "Описана фактическая цена отказа, паузы, ухода и обжалования?", { evidence: true, human: true }),
    C("VOICE_ACCESS", "Проверены признанная форма выражения, слышимость и контроль интерпретации?", { evidence: true, human: true }),
    C("APPEAL_AVAILABLE", "Есть независимый пересмотр и защита от возмездия?", { evidence: true, onNo: "REVIEW" }),
  ], "Локализует власть в интерфейсах, времени, санкциях и праве толкования.", "ON_POWER_OR_HIGH_STAKES"),

  P("V38-NORM-GATE", "NORM-GATE", "GATE", "ACTIVE_TRIGGERED", "MIXED", ["#L638-L672", "#L19911-L19969"], [
    C("NORM_TYPE", "Тип нормы и источник требования названы?", { evidence: true, onNo: "FAIL" }),
    C("COMPETENCE_BURDEN", "Компетенция и носитель бремени публичного оправдания указаны?", { evidence: true, human: true }),
    C("LEGAL_JUST_SPLIT", "Юридическая действительность, легитимность и справедливость разведены?", { human: true, onNo: "FAIL" }),
    C("LESS_RESTRICTIVE", "Рассмотрена менее ограничивающая альтернатива и распределение вреда?", { evidence: true, human: true }),
  ], "Блокирует вывод должного из описания, осуществимости или онтологии.", "ON_NORMATIVE_CLAIM"),

  P("V38-TRUTH-CLAIM", "Протокол истинностного притязания", "GATE", "ACTIVE_TRIGGERED", "MIXED", ["#L9169-L9195"], [
    C("WORUEBER", "Явно указано сущее или дело, о котором утверждается?", { evidence: true, onNo: "FAIL" }),
    C("ACCESS_CHAIN", "Описаны способ обнаружения и посредники доступа?", { evidence: true }),
    C("FALSIFIER", "Указано, что подтвердит или опровергнет формулу?", { evidence: true, onNo: "FAIL" }),
    C("ALTERNATIVE_READING", "Представлено контрчтение и возможное сокрытие?", { evidence: true, human: true }),
    C("REVISION", "Новые данные, меняющие формулу, названы заранее?", { evidence: true }),
  ], "Совмещает предметную проверку, медиаторы доступа и пересмотр без релятивизма.", "ON_TRUTH_CLAIM"),

  P("V38-ANTI-SELF-CIRCULATION", "Протокол против самоциркуляции", "CORE", "ACTIVE_TRIGGERED", "MIXED", ["#L7361-L7380"], [
    C("EXTERNAL_CONSTRAINT", "Есть первичный текст, сцена или данные, ограничивающие тезис извне проекта?", { evidence: true, onNo: "FAIL" }),
    C("NOVELTY_QUARANTINE", "Новый термин имеет незаменимый вопрос и контрпример?", { evidence: true }),
    C("CONSOLIDATION", "Повторы вынесены из активного ядра в архив?", { evidence: true }),
    C("EXTERNAL_FALSIFIABILITY", "Возражение может реально изменить решение, а не быть поглощено теорией?", { human: true, onNo: "FAIL" }),
  ], "Предотвращает доказательство теории её собственным объёмом и словарём.", "AT_VERSION_REVIEW"),

  P("V38-GERMAN-RUSSIAN-CONCEPT", "Немецко-русский протокол понятия", "LANGUAGE", "ACTIVE_TRIGGERED", "MIXED", ["#L25489-L25519"], [
    C("TERM_PHASE", "Точное написание, историческая фаза и функция термина указаны?", { evidence: true, onNo: "FAIL" }),
    C("THREE_TRANSLATIONS", "Сопоставлены минимум три перевода и потери каждого?", { evidence: true }),
    C("NO_MORPH_PROOF", "Словообразование и этимология не используются как доказательство тезиса?", { human: true, onNo: "FAIL" }),
    C("EXAMPLE_COUNTEREXAMPLE", "Даны феноменальный пример и контрпример?", { evidence: true }),
    C("STATUS_ASSIGNED", "Назначен статус: прямой термин, реконструкция, R3/R4T или региональное понятие?", { onNo: "FAIL" }),
  ], "Сохраняет перевод как контролируемое различение, а не равенство терминов.", "ON_TRANSLATION"),

  P("V38-RUSSIAN-LEXICAL", "Русская лексико-феноменологическая деструкция", "LANGUAGE", "ACTIVE_TRIGGERED", "MIXED", ["#L18181-L18218", "#L19456-L19487"], [
    C("CONTEXT_CONSTRUCTION", "Единицей служит конструкция в живом контексте, а не лемма или морфема?", { evidence: true, onNo: "FAIL" }),
    C("LEX_LEVELS", "LEX-R1/R2/R3/R4T и история перевода разведены?", { evidence: true, onNo: "FAIL" }),
    C("CORPUS_NEGATIVE", "Есть корпусные контексты, конкурирующие конструкции и отрицательные случаи?", { evidence: true }),
    C("NO_LANGUAGE_ONTOLOGY", "Языковое различие не повышено до онтологии, психологии народа или нормы?", { human: true, onNo: "FAIL" }),
    C("REVISION_CONDITION", "Минимальное различие и условие его пересмотра сформулированы?", { evidence: true }),
  ], "Отсекает этимологизм и делает русские различия проверяемыми гипотезами.", "ON_RUSSIAN_LANGUAGE_CLAIM"),

  P("V38-TRANSLATION-BRIDGE", "Перевод между несводимыми традициями", "LANGUAGE", "ACTIVE_TRIGGERED", "MIXED", ["#L26442-L26460"], [
    C("SOURCE_QUESTION", "Исходный вопрос и функция понятия в своей традиции указаны?", { evidence: true }),
    C("PROJECT_FUNCTION", "Функция заимствования в проекте названа отдельно?", { evidence: true }),
    C("BRIDGE_TYPE", "Отношение SRC/REC/BRG/COR/CON/GEN типизировано?", { onNo: "FAIL" }),
    C("FORBIDDEN_TRANSFER", "Назван запрещённый перенос между традициями или уровнями?", { evidence: true }),
  ], "Не позволяет полифонии превратиться в эклектическое отождествление.", "ON_CROSS_TRADITION_TRANSFER"),

  P("V38-DASEIN", "Анализ Dasein в русскоязычном тексте", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L1267-L1299"], [
    C("HISTORICAL_LAYER", "Исторический слой и функция Dasein установлены?", { evidence: true, human: true }),
    C("NO_HUMAN_SUBSTITUTION", "Dasein не заменено словом «человек» до установления уровня?", { human: true, onNo: "FAIL" }),
    C("EXISTENCE_SPLIT", "Existenz, existentia, Vorhandensein и Ek-sistenz разведены?", { evidence: true, human: true }),
    C("ANTHROPOLOGY_BOUNDARY", "Зафиксирована граница перехода к философской антропологии?", { evidence: true, human: true }),
  ], "Высокоценный предметный модуль; автоматизируется как экспертный вопросник, не как истинностный классификатор.", "ON_DASEIN"),

  P("V38-HERMENEUTIC-CASE", "Герменевтический анализ случая", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L5413-L5444"], [
    C("FORESTRUCTURE", "Vorhabe, Vorsicht и Vorgriff названы раздельно?", { evidence: true, human: true }),
    C("POSSIBILITY_LEVELS", "Экзистенциальная возможность, фактический доступ и разрешение разведены?", { human: true }),
    C("RIVAL_INTERPRETATION", "Есть конкурентное истолкование и отрицательный случай?", { evidence: true, human: true }),
    C("RESISTANCE", "Учтено сопротивление тела, материала, текста, другого и последствий?", { evidence: true, human: true }),
  ], "Полезен для case review; требует человеческого герменевтического суждения.", "ON_CASE_INTERPRETATION"),

  P("V38-SPEECH-LANGUAGE", "Анализ речи и языка", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L6340-L6371"], [
    C("HISTORICAL_SPEECH_LAYER", "Разведены Rede, фактическая Sprache, поздняя Sage и коммуникационная теория?", { evidence: true, human: true }),
    C("MEDIUM_ACCESS", "Описаны медиум, телесная/сенсорная доступность и посредники?", { evidence: true }),
    C("RIGHTS_OF_SPEECH", "Проверены право говорить, молчать, задавать тему и переистолковывать?", { human: true }),
    C("SILENCE_MODES", "Молчание различено как выбор, ожидание, отказ, невозможность и принуждение?", { evidence: true, human: true }),
  ], "Сильный модуль для поддержанной коммуникации и анализа интерфейсов.", "ON_SPEECH_OR_COMMUNICATION"),

  P("V38-DEATH", "Десятиуровневый анализ смерти", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L10083-L10092"], [
    C("DEATH_TERMS", "Tod, Sterben, Ableben и Verenden разведены?", { evidence: true, human: true }),
    C("ACCESS_AND_LEVEL", "Источник доступа и онтологический/онтический уровень указаны?", { evidence: true }),
    C("BODY_SOCIAL_RISK", "Учтены телесные условия и социальное распределение риска?", { evidence: true, human: true }),
    C("NO_CLINICAL_NORM_TRANSFER", "Философская формула не перенесена в диагноз, рекомендацию или норму без моста?", { human: true, onNo: "FAIL" }),
  ], "Ценный защитный модуль для высокорисковой темы; всегда требует специалиста.", "ON_DEATH_OR_END_OF_LIFE"),

  P("V38-CONSCIENCE", "Анализ «голоса совести»", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L10965-L11005"], [
    C("PHENOMENON_MEDIUM", "Феномен и его медиум описаны без презумпции акустического голоса?", { evidence: true, human: true }),
    C("SOURCE_VOICES", "Публичные, семейные, религиозные, травматические и институциональные голоса проверены?", { human: true }),
    C("SAFETY", "Проверены кризис, принуждение, навязчивость и опасный приказ?", { evidence: true, human: true, onNo: "FAIL" }),
    C("REVOCABILITY", "Решение можно исправить, отвергнуть и отозвать?", { human: true }),
  ], "Снижает риск моральной, клинической и властной гиперинтерпретации.", "ON_CONSCIENCE_OR_INNER_VOICE"),

  P("V38-TEMPORALITY", "Временной анализ феномена", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L11694-L11727"], [
    C("ECSTATIC_UNITY", "Будущее, бывшее и настоящее описаны в единстве, а не как три отрезка?", { human: true }),
    C("MODE_MARKED", "Модус временения указан?", { evidence: true, human: true }),
    C("RHYTHMS_POWER", "Учтены телесные, материальные, институциональные ритмы и владелец срока?", { evidence: true, human: true }),
    C("NO_UNIVERSALIZER", "Временность не превращена в универсальный объяснитель?", { human: true, onNo: "FAIL" }),
  ], "Предметный модуль, полезный как структурированная экспертная проверка.", "ON_TEMPORAL_CLAIM"),

  P("V38-WORLD-TIME", "Анализ временной ситуации и мирового времени", "DOMAIN", "ACTIVE_TRIGGERED", "MIXED", ["#L12389-L12420", "#L33717-L33725"], [
    C("DATABLE_EVENT", "Указаны датирующее событие, протяжённость и время-для?", { evidence: true }),
    C("PUBLIC_SCALE", "Публичная шкала и измерительный прибор описаны?", { evidence: true }),
    C("DEADLINE_OWNER", "Назван институциональный владелец срока и право на паузу?", { evidence: true, human: true }),
    C("CHRONOLOGY_LIMIT", "Хронология не подменяет экзистенциальную временность?", { human: true }),
  ], "Хорошо операционализируемый мост между временной интерпретацией и институтами.", "ON_WORLD_TIME_OR_DEADLINE"),

  P("V38-HISTORICITY", "Историчность и унаследованная возможность", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L13081-L13112", "#L33726-L33733"], [
    C("TRANSMISSION_CHAIN", "Событие, бывший мир, материальный след и способ передачи различены?", { evidence: true, human: true }),
    C("REPEATABLE_POSSIBILITY", "Повторимая возможность отделена от реставрации и приказа традиции?", { human: true }),
    C("EXCLUDED_VOICES", "Отмечены исключённые голоса и политический субъект?", { evidence: true, human: true }),
    C("NORMATIVE_CLAIM", "Нормативное притязание вынесено в отдельный шлюз?", { evidence: true }),
  ], "Удерживает историю от редукции к хронологии или наследованию нормы.", "ON_HISTORICAL_CLAIM"),

  P("V38-TEMPORALITY-BRIDGE", "Шлюз Zeitlichkeit → Temporalität", "DOMAIN", "ACTIVE_TRIGGERED", "HUMAN_REVIEW", ["#L13785-L13820", "#L33734-L33743"], [
    C("SEINSART_SCENE", "Исследуемый Seinsart и феноменальная сцена зафиксированы?", { evidence: true }),
    C("HORIZON_SOURCE", "Горизонтальная схема и первичный источник указаны?", { evidence: true, human: true }),
    C("ACCESS_STRUCTURE_SPLIT", "Условие доступа отделено от структуры бытия?", { human: true, onNo: "FAIL" }),
    C("ALTERNATIVE_HORIZON", "Есть контрпример, альтернативный горизонт и условие пересмотра?", { evidence: true, human: true }),
  ], "Специализированный high-burden bridge; не допускает автоматического принятия.", "ON_TEMPORALITY_TO_TEMPORALITAET"),

  P("V38-GESTELL-4D", "Machenschaft–Gestell–Bestand–Ordering", "DOMAIN", "ACTIVE_TRIGGERED", "MIXED", ["V4D#protocol", "#L17100-L17637"], [
    C("DIACHRONIC_RECONSTRUCTION", "Machenschaft и Gestell связаны явным или оспоримым диахроническим мостом, а не синонимией?", { evidence: true, human: true, onNo: "FAIL" }),
    C("CONCRETE_DISCRIMINATION", "Высокий тезис опирается на конкретные TO4/BS4-профили и counterprofile?", { evidence: true, onNo: "FAIL" }),
    C("TECHNICAL_OBJECT_FIREWALL", "Технический или современный объект сам по себе не считается подтверждением Gestell?", { human: true, onNo: "FAIL" }),
    C("TOTALIZATION_REVIEW", "Эпохальное/универсальное притязание отправлено на независимый review?", { evidence: true, human: true }),
  ], "Интегрирует ценный дискриминационный принцип 4D без подтверждения его 9/9 самоотчёта.", "ON_TECHNOLOGY_GESTELL"),

  P("V38-PREREGISTRATION", "Preregistration исследовательского цикла", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L27893-L27942", "#L33763-L33770"], [
    C("PLAN_FROZEN", "До основной выборки заморожены ID, единица, кодбук, выборка, seed, метрики и пороги?", { evidence: true, onNo: "FAIL" }),
    C("KILL_FROZEN", "KILL-критерии и действия при провале зафиксированы заранее?", { evidence: true, onNo: "FAIL" }),
    C("DEVIATION_POLICY", "Изменения оформляются как явные отклонения с сохранением исходного плана?", { evidence: true, onNo: "FAIL" }),
  ], "Прямо исполнимо через freeze/verify; ключевой вклад v3.8 в автоматический инструмент.", "BEFORE_DATA_INSPECTION"),

  P("V38-DATA-GATE", "DATA/AUTH/LIC/CODER-шлюз", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L28070-L28112", "#L33771-L33778"], [
    C("DATA_LEGITIMATE", "Данные доступны легитимно и их происхождение проверяемо?", { evidence: true, onNo: "SUSPEND" }),
    C("AUTH_EXPLICIT", "Авторизация и ограничения доступа не предполагаются молча?", { evidence: true, onNo: "SUSPEND" }),
    C("LICENSE_EXPLICIT", "Лицензия разрешает заявленную обработку и распространение?", { evidence: true, onNo: "SUSPEND" }),
    C("CODERS_AVAILABLE", "Назначено требуемое число независимых кодировщиков?", { evidence: true, onNo: "SUSPEND" }),
  ], "Автоматически блокирует псевдоэмпирический вывод при отсутствии данных или независимости.", "BEFORE_EMPIRICAL_RUN"),

  P("V38-BLIND-ANNOTATION", "Независимое слепое кодирование", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L28004-L28037", "#L33788-L33795"], [
    C("BLIND_PHASES", "Фазы CONTEXT/MASK/L2-ONLY/META-NULL и скрываемые поля определены заранее?", { evidence: true, onNo: "FAIL" }),
    C("NO_CONTACT", "До расчёта метрик кодировщики не обменивались решениями?", { evidence: true, onNo: "FAIL" }),
    C("RAW_LABELS_PRESERVED", "Исходные метки сохранены отдельно от adjudication?", { evidence: true, onNo: "FAIL" }),
    C("CODER_IDENTITY", "Разные идентичности кодировщиков проверены; повтор одного аналитика не считается IAA?", { evidence: true, onNo: "FAIL" }),
  ], "Снижает лексический, гипотезный и авторский прайминг.", "ON_ANNOTATION_STUDY"),

  P("V38-RELIABILITY", "Шлюз межэкспертной воспроизводимости", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L28038-L28069", "#L33779-L33787"], [
    C("ALPHA_REPORTED", "Опубликованы nominal α и доверительный интервал, а не только процент совпадений?", { evidence: true, onNo: "FAIL" }),
    C("RARE_CODES", "Показаны матрица ошибок и устойчивость редких кодов?", { evidence: true }),
    C("THRESHOLD_APPLIED", "Заранее заданный порог применён без ретроспективного снижения?", { evidence: true, onNo: "FAIL" }),
    C("VALIDITY_SEPARATE", "Надёжность не объявлена валидностью или онтологической истинностью?", { human: true, onNo: "FAIL" }),
  ], "Прямо исполнимо через модуль Krippendorff α и bootstrap CI.", "AFTER_BLIND_ANNOTATION"),

  P("V38-NEGATIVE-ABLATION", "Отрицательные тесты и абляция", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L26905-L26936", "#L28070-L28100"], [
    C("NEGATIVE_TESTS_FIXED", "Операции маскирования, удаления столбца/метаданных и перестановки определены заранее?", { evidence: true }),
    C("ABLATION_DIMENSIONS", "Каждое измерение удаляется поочерёдно с измеримым критерием потери?", { evidence: true }),
    C("CONTROL_MODELS", "Есть baseline без рамки и сильная композиция конкурентов?", { evidence: true }),
    C("FAIL_ACTION", "Для каждого провала задано объединение, понижение или удаление?", { evidence: true, onNo: "FAIL" }),
  ], "Проверяет добавочную ценность интерфейса, а не только внутреннее согласие.", "AFTER_BASELINE"),

  P("V38-SNAPSHOT-REPLICATION", "SNAP и репликационный протокол", "RESEARCH", "ACTIVE_RESEARCH", "DETERMINISTIC", ["#L30413-L30442", "#L33744-L33762"], [
    C("SNAP_METADATA", "Сохранены корпус, версия/дата, запрос, фильтры, знаменатель, seed и исключения?", { evidence: true, onNo: "FAIL" }),
    C("STABLE_IDS", "Единицы имеют устойчивые ID и дедуплицированы до разметки?", { evidence: true }),
    C("GENRE_EPOCH", "Анализ повторён по жанрам и эпохам?", { evidence: true }),
    C("DATASET_SEPARATE", "Полные выгрузки и решения хранятся отдельно от мастер-документа?", { evidence: true }),
  ], "Делает корпусный результат воспроизводимым и предотвращает смешение снимков.", "ON_CORPUS_STUDY"),

  P("V38-MASTER-UPDATE", "Обновление мастер-документа", "GOVERNANCE", "ACTIVE_CORE", "DETERMINISTIC", ["#L26954-L26966", "#L33661-L33715"], [
    C("MATERIAL_CHANGE", "Версия меняет вопрос, различение, статус, контрпример или маршрут?", { evidence: true, onNo: "FAIL" }),
    C("DECISION_REGISTER", "Записано: сохранено, объединено, удалено, понижено, приостановлено?", { evidence: true }),
    C("NEGATIVE_PRESERVED", "Отрицательные результаты и прежняя формула сохранены в архиве?", { evidence: true, onNo: "FAIL" }),
    C("REGISTRIES_UPDATED", "Обновлены реестр, матрица, зависимости, контрпримеры и журнал?", { evidence: true }),
  ], "Исполнимое управление изменениями и защита от инфляции версий.", "AT_RELEASE"),

  P("V38-NEUTRAL-DESTRUCTION", "Нейтральная деструкция", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L25861-L25891", "#L20095-L20137"], [
    C("PRESTRUCTURE_EXPLICIT", "Предструктура и привилегированный вопрос названы?", { evidence: true, human: true }),
    C("VISIBLE_HIDDEN", "Для каждой категории указано, что она открывает и скрывает?", { human: true }),
    C("REVERSIBLE", "Категориальную разметку можно снять без потери исходного материала?", { human: true }),
    C("UNRESOLVED_END", "Финал сохраняет нерешённые альтернативы вместо обязательной доктрины?", { evidence: true, human: true }),
  ], "Сохраняется как обзорный режим; основные функции поглощены D2.8.", "EXPLICIT_OPTIONAL"),

  P("V38-REGIONAL-CASE", "Анализ конкретного случая", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L20138-L20179"], [
    C("FACT_INTERPRETATION", "Факт, переживание, интерпретация и социальное условие разведены?", { evidence: true, human: true }),
    C("CYCLE", "Реконструирован цикл ситуации, толка, ответа и последствий?", { evidence: true, human: true }),
    C("SMALL_TEST", "Альтернатива проверяется малым обратимым действием?", { evidence: true, human: true }),
    C("REVIEW_EFFECT", "Задан критерий оценки последствий и пересмотра?", { evidence: true }),
  ], "Полезен как прикладной case-template, но не доказывает онтологию.", "EXPLICIT_OPTIONAL"),

  P("V38-RESPONSE-EVENT", "Анализ ответного события", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L21525-L21556"], [
    C("REACTION_RESPONSE_ACTION", "Реакция, присвоенный ответ, действие и поступок разведены?", { human: true }),
    C("ACCESS_POWER_RISK", "Доступные ответы оценены с учётом власти, зависимости, ресурсов и риска?", { evidence: true, human: true }),
    C("CONSEQUENCES_VOICE", "Получатели последствий и их возможность возразить указаны?", { evidence: true, human: true }),
    C("DIGNITY_BOUNDARY", "Интерпретация не нарушает достоинство, молчание и границы компетенции?", { human: true, onNo: "FAIL" }),
  ], "Содержательно ценный региональный модуль; вынесен из ядра ответности.", "EXPLICIT_OPTIONAL"),

  P("V38-PROMISE", "Анализ обещания", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L22370-L22418"], [
    C("FORMULA_UNDERSTANDING", "Точная формула и совпадение понимания сторон зафиксированы?", { evidence: true, human: true }),
    C("VOLUNTARY_FEASIBLE", "Добровольность, возможность, срок и условия проверены?", { evidence: true, human: true }),
    C("RELIANCE", "Решения адресата, построенные на слове, указаны?", { evidence: true, human: true }),
    C("REPAIR", "Разведены исправимый и необратимый ущерб; задана будущая практика?", { evidence: true, human: true }),
  ], "Полезен для прикладного анализа обязательств, но не относится к автоматическому CORE.", "EXPLICIT_OPTIONAL"),

  P("V38-FIDELITY", "Анализ верности", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L22868-L22920"], [
    C("OBJECT_OF_FIDELITY", "Названо, чему сохраняется верность: букве, человеку, делу, правде или образу?", { evidence: true, human: true }),
    C("CHANGE_RECONSIDERED", "Изменение обстоятельств и конфликт верностей учтены?", { human: true }),
    C("HARM_NOT_HIDDEN", "Верность не используется для сокрытия вреда или запрета выхода?", { human: true, onNo: "FAIL" }),
    C("REVISION_POSSIBLE", "Сохраняется возможность правдивого пересмотра?", { human: true }),
  ], "Содержательно полезен, но частично перекрыт NORM/POWER и promise-модулем.", "EXPLICIT_OPTIONAL"),

  P("V38-LIVING-BODY", "Анализ живого тела", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L23796-L23840"], [
    C("LEIB_KOERPER", "Живое тело, физическое тело, схема и образ тела разведены?", { evidence: true, human: true }),
    C("ACCESS_VARIATION", "Боль, усталость, сон, возраст, инвалидность и поддержка не сведены к дефициту?", { human: true }),
    C("FIRST_THIRD_PERSON", "Асимметричные доступы первого и третьего лица сохранены?", { human: true }),
    C("NO_NORMAL_BODY", "Один телесный стандарт не объявлен универсальной нормой?", { human: true, onNo: "FAIL" }),
  ], "Ценный защитный модуль для телесных и поддержанных действий.", "EXPLICIT_OPTIONAL"),

  P("V38-POWER-CASE", "Властный анализ случая", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L24555-L24612"], [
    C("CONTROL_RESOURCES", "Контроль сведений, времени, пространства, ресурсов и технологий нанесён на карту?", { evidence: true, human: true }),
    C("FORMAL_REAL_ALTERNATIVES", "Формальные альтернативы отделены от реально безопасных?", { human: true }),
    C("CUMULATIVE_PATTERN", "Эпизод отделён от накопительного паттерна контроля?", { evidence: true, human: true }),
    C("COLLECTIVE_OPTION", "Проверена коллективная форма изменения распределения риска?", { human: true }),
  ], "Детализирует POWER-GATE для прикладных случаев.", "EXPLICIT_OPTIONAL"),

  P("V38-NORM-INSTITUTION", "Нормативно-институциональный анализ", "ARCHIVAL_DERIVATIVE", "OPTIONAL_ARCHIVAL_DERIVATIVE", "HUMAN_REVIEW", ["#L25241-L25307"], [
    C("NORM_COMPETENCE", "Тип нормы, адресат, компетенция и механизм поддержания указаны?", { evidence: true, human: true }),
    C("PROCEDURAL_QUALITY", "Публичность, понятность, перспективность, равенство применения и участие проверены?", { evidence: true, human: true }),
    C("REAL_ACCESS_APPEAL", "Реальный доступ к праву, мотивировке, независимой апелляции и защите существует?", { evidence: true, human: true }),
    C("REPEAL_TRIGGER", "Контрпримеры и последствия, требующие пересмотра или отмены, названы?", { evidence: true }),
  ], "Детализирует NORM-GATE для институционального аудита.", "EXPLICIT_OPTIONAL"),
];

const registry = {
  registry_version: "V38-PROTOCOLS-1.0",
  generated_at: "2026-08-11T12:00:00Z",
  source: {
    title: "Вопрос о бытии и русский язык — каноническая редакция v3.8",
    document_sha256: "8d9ae11ea434a2a8e522bd18cf1b351434d20c890c44ce8a49f2d71aeec425c7",
    extract_sha256: "e6ed2875982862cd9fb3aafd98ff4a3faba8c936e1893412ba7f265d95e65466",
    extract_path: "vendor/v38/extract/canonical_v3.8.md",
  },
  claim_ceiling: "PROTOCOL_CONFORMANCE_AND_REVIEW_ROUTING_ONLY",
  answer_statuses: ["YES", "NO", "UNKNOWN", "NA"],
  protocols,
};

await writeFile(path.join(root, "config", "protocol_registry.json"), `${JSON.stringify(registry, null, 2)}\n`, "utf8");

const headingText = await readFile(path.join(root, "vendor", "v38", "extract", "protocol_headings.txt"), "utf8");
const occurrences = headingText.trim().split(/\r?\n/).map((line, index) => {
  const match = line.match(/^(\d+):(#+)\s+(.+)$/u);
  if (!match) throw new Error(`Unparseable protocol heading: ${line}`);
  const lineNumber = Number(match[1]);
  const title = match[3];
  const archived = (lineNumber >= 19658 && lineNumber < 25447) || (lineNumber >= 29227 && lineNumber < 30794);
  const superseded = /предыдущ|прежн|сравнительный аудит версий|ретроспекц/i.test(title);
  const kind = /kill/i.test(title) ? "KILL" : /шлюз|gate/i.test(title) ? "GATE" : /аудит|контрпроверк/i.test(title) ? "AUDIT" : /протокол/i.test(title) ? "PROTOCOL" : "CONTROL";
  return {
    occurrence_id: `V38-OCC-${String(index + 1).padStart(3, "0")}`,
    line: lineNumber,
    locator: `#L${lineNumber}`,
    heading_level: match[2].length,
    title,
    kind,
    source_status: superseded ? "SUPERSEDED_OR_RETROSPECTIVE" : archived ? "ARCHIVAL" : "CURRENT",
  };
});

const occurrenceBundle = {
  inventory_version: "V38-PROTOCOL-OCCURRENCES-1.0",
  generated_at: "2026-08-11T12:00:00Z",
  source_extract_sha256: registry.source.extract_sha256,
  scope_note: "Exhaustive inventory of headings explicitly naming a protocol, gate, audit, countercheck, kill criterion or closely related control in the canonical Markdown extraction.",
  count: occurrences.length,
  counts_by_status: Object.groupBy ? Object.fromEntries(Object.entries(Object.groupBy(occurrences, (item) => item.source_status)).map(([key, value]) => [key, value.length])) : occurrences.reduce((acc, item) => ({ ...acc, [item.source_status]: (acc[item.source_status] ?? 0) + 1 }), {}),
  occurrences,
};
await writeFile(path.join(root, "vendor", "v38", "protocol_occurrences.json"), `${JSON.stringify(occurrenceBundle, null, 2)}\n`, "utf8");

const hash = createHash("sha256").update(JSON.stringify(registry)).digest("hex");
console.log(`Built ${protocols.length} canonical protocol families and ${occurrences.length} source occurrences; registry sha256=${hash}.`);
