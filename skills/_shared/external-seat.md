# External seat — внешнее кресло в совете по решениям (v1.43.0)

Расширение идеи `/cross-review` с диффов кода на **решения** (архитектура, план,
рискованная миграция): когда внутренний скептик (devils-advocate, /grill-me)
отработал, опционально добавить за стол ОДНУ чужую модель — у неё другое
обучение и другие слепые зоны, чем у всех Claude-ролей сразу. Это и есть
рабочая форма «совета моделей»: роли дают разные углы, внешнее кресло даёт
другую модель; синтез делает главный агент.

## Инварианты (те же, что у /cross-review — без исключений)

1. **Opt-in egress.** Кресло активно ТОЛЬКО при явном согласии на внешнюю
   отправку: env `CROSS_REVIEW_EGRESS_OK=1` или маркер `.cross-review-egress-ok`
   в корне репо. Жёсткий off: `ITD_CROSS_REVIEW=0`. Без opt-in — шаг молча
   пропускается, внутренний скептик остаётся единственным.
2. **Scrub перед отправкой.** Синопсис решения проходит тот же scrub, что дифф
   в `skills/cross-review/references/cli-adapters.md` §1 (ключи, токены,
   email, `password=`). Живой кред после scrub → НЕ отправлять, пропустить шаг.
3. **Fail-open, не гейт.** Ошибка/квота/таймаут CLI → отметить «внешнее кресло
   недоступно (<причина>)» и продолжить. Решение никогда не блокируется
   отсутствием внешней модели.
4. **Provenance.** В синтезе всегда указывается, какая модель сидела в кресле
   (codex / gemini / кресло пустовало) — мнение без подписи не мнение.
5. **Деградация: codex → gemini → SKIP.** В отличие от /cross-review здесь НЕТ
   native-fallback: внутренний adversarial уже в комнате (devils-advocate /
   сам /grill-me) — дублировать его Claude-ролью бессмысленно, ценность кресла
   именно в чужой модели.
6. **Не гейт /review и не пишет его сентинел.** Как и /cross-review, внешнее
   кресло не участвует в DoD-//review-гейтах и НИКОГДА не создаёт
   `claude-review-done-*` маркер — оно применяется к решениям, не к диффам
   кода; обязательный /review остаётся нетронутым флором.

## Инвокация

Технически — те же адаптеры, что `skills/cross-review/references/cli-adapters.md`
(stdin-from-file для больших синопсисов, `-c`-override на config-error, timeout
~120s). Промпт для РЕШЕНИЯ (не диффа):

```
You are an INDEPENDENT external seat on a design council. The plan below was
already stress-tested by an internal adversarial reviewer of a DIFFERENT model
family; your value is finding what that family systematically misses. Attack:
hidden assumptions, failure modes at scale, operational cost, simpler
alternatives, irreversibility. Return a short ranked list (problem -> why it
matters -> concrete alternative). If the plan is genuinely sound, say so in
one line — do not invent objections.
--- DECISION SYNOPSIS (secrets redacted) ---
<scrubbed synopsis: контекст, выбранный вариант, отвергнутые альтернативы,
ключевые риски по мнению внутреннего скептика>
```

Синопсис — 30–60 строк выжимки, НЕ полный документ: контекст и ограничения,
выбранное решение, 2–3 отвергнутые альтернативы с причинами, вердикт и
топ-вызовы внутреннего скептика.

## Синтез (главный агент)

- **Согласие** внутреннего и внешнего по пункту → поднять приоритет пункта
  (две независимые семьи моделей сошлись — сигнал сильный).
- **Расхождение** → НЕ выбирать молча: показать пользователю оба мнения с
  provenance, решение за ним.
- **Уникальные находки кресла** → влить в общий список с пометкой `[external]`.
- Кресло не имеет права вето — его выход всегда advisory (инвариант 3).

## Где применяется

- `/grill-me` — финальный шаг стресс-теста (после внутренних осей).
- `/blueprint` Step 2.5 — рядом с devils-advocate (Full mode).
- Дальше по сигналу: /strategy (pivot-ADR), /migrate-prod (план миграции).
