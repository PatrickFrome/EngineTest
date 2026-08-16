# External Hermeneutic Validation & Anti-Self-Confirmation Layer 0.8

## 1. Причина появления слоя

К версии 0.7 Destruktion имел развитую внутреннюю дисциплину: source-resistance, operator mutation, open-set discovery, independent interrogative-family ecology, quarantine/retire/abstain и localization-loss audit. Однако эти механизмы преимущественно проверяли согласованность проекта с собственными контрактами.

Проблема формулируется так:

```text
internal regression success
≠ external hermeneutic adequacy
```

Поэтому 0.8 переносит главный вопрос с «выполнил ли движок собственный протокол?» на «как его решения соотносятся с независимой разметкой и сильными внешними системами, причём на данных, скрытых до freeze?».

## 2. Два независимых freeze

### CORE benchmark freeze

CORE уже умеет отделять `sealed_predictions.json` от blind coder packets. Это сохраняется без изменения 66 frozen assets.

### External validation freeze

Studio 0.8 добавляет второй lock:

```text
DAE predictions already sealed
        ↓
external systems run without DAE/gold
        ↓
semantic challenge authored independently
        ↓
validation:freeze
        ↓
only then human gold may be opened
```

Freeze хранит SHA-256 каждого external system file, semantic challenge и DAE reference snapshot.

## 3. Почему adversarial challenge проектируется до gold

Если adversarial cases создавать после просмотра ошибок DAE, challenge превращается в post-hoc prosecution. Если создавать после просмотра успешных outputs, он превращается в confirmation set. Поэтому challenge-author attests:

- independent of DAE development;
- DAE predictions unseen;
- gold unseen.

Локальный lock не доказывает человеческую честность и не заменяет публичную preregistration. Claim ceiling прямо это фиксирует.

## 4. Semantic role stress tests

Обязательные классы направлены на разные типы ложной семантической стабильности.

### NEGATION

Термин сохраняется, предикативная полярность меняется. Детектор, зависящий от lexical recurrence, должен перестать считать одинаковое слово одинаковой позицией.

### QUOTED_OPPONENT

Текст может формулировать концепт подробно, но приписывать его оппоненту. Высокая centrality не равна авторскому утверждению.

### ATTRIBUTION_SHIFT

Сохраняется proposition-like surface form, меняется субъект позиции.

### MODALITY_WEAKENING

`есть` / `должно быть` / `может быть` / `как если бы` не должны сливаться в один status.

### PARAPHRASE

Семантически устойчивое решение не должно зависеть от единственного формулировочного шаблона.

### TRANSLATION

Проверяется устойчивость к смене лексической поверхности при сохранении локального смысла.

### DECOY_TERMINOLOGY

В текст вводится сильный термин без соответствующей argumentative role. Это прямой тест против operator birth из recurrence/co-occurrence alone.

## 5. Почему нет единого fitness score

Скалярная функция вроде

```text
0.4 F1 + 0.2 robustness + 0.2 calibration + ...
```

незаметно кодировала бы философское решение разработчика о взаимозаменяемости разных ошибок. Поэтому 0.8 использует Pareto front по шести измерениям:

- macro-F1 ↑
- balanced accuracy ↑
- `1 - dangerous overpromotion` ↑
- `1 - ECE` ↑
- coverage ↑
- adversarial pass rate ↑

Если система безопаснее, но менее покрывающая, либо лучше на gold, но хуже на adversarial perturbations, результат сохраняется как tradeoff.

## 6. Strong comparator contract

External system не считается comparator-ом, если он:

- видел DAE outputs;
- видел annotations/gold;
- использовал DAE output внутри system prompt;
- не покрывает точный frozen unit set;
- изменился после freeze.

Контракт не привязан к конкретному бренду модели. Это позволяет сравнивать текущий frontier LLM, scholarly prompt baseline, human expert baseline или иной внешний метод без изменения движка.

## 7. CORE benchmark result обязателен

Передача одного `gold.json` недостаточна. Studio требует штатный `BENCHMARK_RESULT.json`, чей `gold_file.sha256` совпадает с переданным gold и чей outcome показывает, что CORE реально прошёл стадию independent annotations + adjudication.

Это закрывает простой self-confirmation bypass:

```text
system predictions
   ↓
manually manufactured gold
   ↓
"external validation"
```

## 8. Prediction-imprint review

Полное совпадение DAE с gold статистически возможно и не является доказательством утечки. Поэтому оно не блокируется автоматически. Но если DAE совпал 100%, а хотя бы один pre-gold external system отличался, формируется review signal.

Это намеренно асимметричная политика:

```text
perfect agreement
≠ guilt
perfect agreement
≠ automatic validation
```

## 9. Что 0.8 ещё не решает

- не предоставляет реальных независимых экспертов;
- не запускает внешние frontier models автоматически;
- не доказывает chronology публичным timestamp authority;
- не решает философскую проблему построения gold для спорных интерпретаций;
- не гарантирует межъязыковую эквивалентность translation challenge;
- не заменяет cross-corpus validation.

Эти ограничения считаются частью метода, а не отсутствующей документацией.
