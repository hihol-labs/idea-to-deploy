# Document Templates Reference

## STRATEGIC_PLAN.md Template

```markdown
# Стратегический план: {Project Name}

## 1. Описание идеи
Что делает продукт, для кого, как работает.

## 2. Целевая аудитория
2-3 персоны с описанием болей:
| Персона | Роль | Боль | Как решаем |
|---------|------|------|-----------|

## 3. Конкурентный анализ
| Конкурент | Что делает | Слабые стороны | Наше отличие |
|-----------|-----------|---------------|-------------|

## 4. УТП
Одно предложение, которое отвечает "почему мы, а не конкурент?"

## 5. Бизнес-модель
Тарифы, unit-экономика, LTV, CAC.

## 6. Технологический стек
| Компонент | Технология | Почему |
|-----------|-----------|--------|

## 7. Timeline
| Неделя | Этап | Результат |
|--------|------|----------|

## 8. KPIs
| Метрика | Цель (1 мес) | Цель (3 мес) | Цель (6 мес) |
|---------|-------------|-------------|-------------|

## 9. Риски
| Риск | Вероятность | Влияние | Митигация |
|------|------------|---------|-----------|

## 10. Бюджет
| Статья | Ежемесячно | Комментарий |
|--------|-----------|-------------|

## 11. Feature Roadmap (приоритизация)

### MoSCoW

| Фича | MoSCoW | Обоснование |
|------|--------|-------------|
| {feature} | Must / Should / Could / Won't | {why} |

### RICE-скоринг (Must + Should)

| Фича | Reach | Impact | Confidence | Effort (дней) | RICE Score |
|------|-------|--------|-----------|---------------|------------|
| {feature} | 1-10 | 1-5 | 50-100% | N | R×I×C/E |

Порядок реализации: по убыванию RICE Score.
```

## PROJECT_ARCHITECTURE.md Template

Key sections and expected level of detail:
- Database: ALL tables with ALL fields, types, constraints, indexes
- API: ALL endpoints with method, path, request/response bodies
- Env vars: ALL variables with descriptions and example values
- Docker: Full docker-compose.yml structure
- Auth: Complete flow diagram (ASCII)

## IMPLEMENTATION_PLAN.md Template

Each step must follow this format:
```markdown
## ШАГ N: НАЗВАНИЕ
**Цель:** что будет работать после этого шага
**Время:** ~X часов
**Контекст:** PROJECT_ARCHITECTURE.md разделы X, Y
**Задачи:**
1. Создать `path/to/file.py` — конкретное описание
2. Создать `path/to/other.py` — конкретное описание
**Проверка:**
- `command to verify`
- `curl http://localhost:port/endpoint`
**Коммит:** "step-N: краткое описание"
```

## PRD.md Template

User stories format:
```
Как [роль], я хочу [действие], чтобы [результат].
Приоритет: P0/P1/P2
Критерии приёмки:
- [ ] Конкретная проверка 1
- [ ] Конкретная проверка 2
```

## README.md Template

Must include "Quick Start" that gets the project running in under 30 seconds:
```bash
git clone ...
cp .env.example .env
docker-compose up -d
# Open http://localhost:3000
```
