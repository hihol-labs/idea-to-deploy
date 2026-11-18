# PRD — nginx-log-report

## Цель и границы релиза

Дать инженеру DevOps/SRE локальный отчёт по конечному фрагменту nginx access log. P0 — все функции первого релиза за один уик-энд с бюджетом $0. P1 и P2 описывают возможное развитие после MVP. Порог для 1 GB — строго меньше 30 секунд на эталонном ноутбуке по [протоколу архитектуры](PROJECT_ARCHITECTURE.md#производительность-и-проверка).

## User Stories

- As a DevOps engineer, I want to read one nginx log from a file or stdin so that I can diagnose an incident with the snapshot I already have. **P0**
  - [ ] Один файл, перенаправленный stdin без пути и явный «-» дают одинаковый результат. После повреждённой строки разбор возобновляется, при наличии валидных строк отчёт сопровождается одним предупреждением в stderr.
  - [ ] Строка длиной 65 536 байт обрабатывается, если её поля корректны. Более длинная строка засчитывается как один пропуск. Пустой или полностью повреждённый вход даёт код «3» и пустой stdout.
- As an on-call SRE, I want the ten most active IPs so that I can identify the main sources of requests. **P0**
  - [ ] Все валидные записи участвуют в подсчёте, разные записи одного IPv6 приводятся к одному ключу. При 11 IP в отчёт входят ровно 10 по числу запросов и ASCII-порядку ключей при равенстве.
- As a pipeline operator, I want a distinct error for aggregate capacity so that I can reject a run before consuming an incomplete report. **P0**
  - [ ] На точных границах 250 000 ключей и 32 MiB их байтов подсчёт продолжается для повторов. Превышение любого предела новой записью даёт код «4», пустой stdout и диагностику исчерпанного лимита.
  - [ ] Запись с несколькими новыми ключами проверяется целиком. При отказе накопитель сохраняет состояние до принятия этой записи.
- As an on-call SRE, I want the ten routes with the most 4xx and 5xx responses so that I can prioritize the most affected paths. **P0**
  - [ ] Статусы 400 и 599 учитываются, 399 — исключается. Запросы к «/a?x=1» и «/a?x=2» объединяются по «/a». При отсутствии ошибок топ пуст.
- As a platform engineer, I want the percentage of requests by UTC hour so that I can compare activity across log excerpts with different offsets. **P0**
  - [ ] Есть 24 строки «00»–«23» UTC, включая нулевые корзины. Для каждой используется «100 × hourly_request_count / total_valid_requests» с округлением до сотых.
  - [ ] При смешанных положительных и отрицательных смещениях, переходе через полночь и нескольких датах совпадающие часы суток UTC объединяются.
- As a platform engineer, I want the share of distinct User-Agents so that I can gauge client variety in the snapshot. **P0**
  - [ ] Доля равна «100 × distinct_user_agents / total_valid_requests». Два одинаковых значения, одно другое и один отсутствующий UA в четырёх запросах дают 2 различных значения и 50,00%.
- As an automation engineer, I want JSON so that I can ingest structured results and keep diagnostics separate. **P0**
  - [ ] «--json» даёт один объект по схеме архитектуры в stdout без ANSI. Счётчики и проценты читаются как числа.
- As a DevOps engineer, I want CSV so that I can compare run outputs in tabular tools. **P0**
  - [ ] «--csv» даёт заголовок «metric,key,count,percentage», корректное экранирование и те же значения, что JSON. Конфликт «--json --csv» возвращает «2» до открытия входа.
- As an on-call SRE, I want a readable color report so that I can inspect results directly during triage. **P0**
  - [ ] Без флагов отображаются четыре метрики и итоги. При поддержке терминалом включается цвет, перенаправленный вывод без ANSI. Пути со скобками показываются буквально.
- As a DevOps engineer, I want to install the CLI through pip so that I can run it in my Python 3.11 environment. **P0**
  - [ ] Собранный wheel устанавливается в чистое окружение Python 3.11, откуда работают «nginx-log-report --help» и все три режима вывода на контрольном файле.
- As a DevOps engineer, I want to feed a gzip log directly so that I can skip a separate decompression command. **P1, после MVP**
- As an SRE, I want to adjust the ranking size so that I can examine more of the long tail when needed. **P2, после MVP**

## Функциональные требования

| Приоритет | Объём |
|---|---|
| P0 | Локальный файл или stdin, nginx combined с escape=default, origin-form и OPTIONS *, четыре точные метрики, JSON/CSV/Rich, установка через pip |
| P0 | Контракт «0/1/2/3/4» из [CLI Interface](PROJECT_ARCHITECTURE.md#cli-interface). «0» — успех или справка, «1» — сбой I/O или прерывание, «2» — ошибка вызова, «3» — нет валидных записей, «4» — исчерпан бюджет уникальных ключей |
| P1 | Прямое распаковывание gzip для оценки после релиза |
| P2 | Настраиваемый размер топа для оценки после релиза |

Тестовые и замерочные журналы синтетические. Данные локального журнала обрабатываются в процессе. Диагностика исключает исходные строки, User-Agent и query string. Топы содержат IP и пути, поэтому отчёт следует хранить с теми же ограничениями доступа, что и журнал.

## Сквозной пример приёмки

Четыре валидные строки и одна повреждённая строка между первой и второй. В валидных строках использовать метод GET, версию HTTP/1.1, дефис в полях пользователя и referer, размер тела 0. Повреждённая строка — «broken».

| IP | Время | Request-target | Статус | User-Agent |
|---|---|---|---:|---|
| 2001:0db8:0:0:0:0:0:1 | 02/Jan/2025:01:30:00 +0200 | /a?x=1 | 404 | Bot |
| 2001:db8::1 | 03/Jan/2025:23:55:00 +0000 | /a?x=2 | 500 | Bot |
| 192.0.2.1 | 02/Jan/2025:00:10:00 -0130 | /b | 429 | Browser |
| 192.0.2.1 | 02/Jan/2025:00:30:00 +0030 | /b | 200 | - |

Ожидаются код «0», одна диагностика о пропуске, «total_valid_requests=4» и «malformed_lines=1». Топ IP — «192.0.2.1» и «2001:db8::1» по 2 запроса, в этом порядке. Топ ошибок — «/a» с 2 ответами и «/b» с 1. Часы «00» и «01» содержат по одному запросу и 25,00%, «23» — 2 и 50,00%. Остальные 21 корзина нулевые. Доля User-Agent — 2 и 50,00%.

## Критерии выпуска и остановки

Релиз готов после зелёного прогона модульных и сквозных проверок, сверки всех форматов, установки чистого wheel и успешного эталонного замера. Если хотя бы один из трёх тестовых запусков 1 GB занимает 30 секунд или больше, превышен потолок RSS, расходятся форматы или любая фатальная ошибка анализа выдаёт отчёт с кодом «0», выпуск останавливается. Следующий шаг — исправить измеренное расхождение и повторить проверку. Тесты, корпус и упаковка перечислены в [плане](IMPLEMENTATION_PLAN.md). По истечении уик-энда нерешённый блокер фиксируется с результатами замеров, выпуск откладывается.

## Вне объёма MVP

Аутентификация, БД, HTTP API, сервер, облако, Kubernetes, daemon/follow, произвольный log_format, несколько файлов за вызов, прямой gzip, изменения размера топа и приблизительные агрегаты.
