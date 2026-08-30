# py2gis-agents

Компактный MCP-сервер для анализа инфраструктуры по данным 2GIS. Сервер
предоставляет модели ровно два высокоуровневых инструмента и не открывает
низкоуровневые методы Places, Geocoder, Suggest и Categories.

## Инструменты

| Инструмент | Результат |
| --- | --- |
| `dgis_analyze_social_infrastructure` | Социальные услуги, повседневные сервисы, досуг и качество среды |
| `dgis_analyze_transport_infrastructure` | Общественный транспорт и транспортные узлы |

Оба инструмента принимают одну точку WGS84, радиус, режим поиска и лимит
объектов на категорию:

- `latitude`, `longitude` — центр поиска;
- `radius_m` — радиус от 1 до 50 000 м, по умолчанию 5 000 м;
- `mode` — `minimal` или `extended`;
- `limit_per_category` — от 1 до 20 ближайших объектов в ответе.

`minimal` выполняет один экономный запрос на каждую категорию. `extended`
использует дополнительные поисковые формулировки и расходует больше запросов
к API, но увеличивает полноту результата.

### Социальная инфраструктура

- Обязательные услуги: образование, здравоохранение, экстренные службы.
- Повседневные услуги: магазины, аптеки, банки, почта, государственные услуги.
- Досуг и качество среды: спорт, культура, парки и зоны отдыха.

### Транспортная инфраструктура

- Общественный транспорт: остановки, железнодорожные станции и платформы,
  автовокзалы и автостанции.
- Транспортные узлы: железнодорожные объекты, аэропорты, порты,
  логистические терминалы.

Дороги намеренно не включены: их геометрию и классификацию получает
`pyosm-agents` из OpenStreetMap.

## Установка

Требуется Python 3.10 или новее и ключ 2GIS Search API.

```bash
git clone git@github.com:SergeyMalashenko/py2gis-agents.git
cd py2gis-agents
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[mcp]'
cp .env.example .env
```

Укажите ключ в `.env`:

```dotenv
PY2GIS_API_KEY="ваш_ключ_2gis"
```

Поддерживается и прежнее имя переменной `DGIS_API_KEY`. Ключ никогда не
возвращается MCP-клиенту и очищается из диагностических сообщений.

## Запуск Streamable HTTP

```bash
source .venv/bin/activate
py2gis-mcp \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8003
```

MCP endpoint: `http://127.0.0.1:8003/mcp`.

Для `stdio` достаточно запустить `py2gis-mcp` без аргументов. Не подключайте
одновременно HTTP- и stdio-вариант одного сервера в Hermes: модель увидит
дублирующиеся инструменты.

## Проверка через MCP Inspector

Список инструментов:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8003/mcp \
  --transport http \
  --method tools/list
```

Социальная инфраструктура:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8003/mcp \
  --transport http \
  --method tools/call \
  --tool-name dgis_analyze_social_infrastructure \
  --tool-args-json '{
    "latitude": 56.0678,
    "longitude": 43.6031,
    "radius_m": 5000,
    "mode": "minimal",
    "limit_per_category": 5
  }'
```

Для транспортного отчёта замените имя инструмента на
`dgis_analyze_transport_infrastructure`.

## Hermes Agent

При уже запущенном HTTP-сервере:

```bash
hermes mcp add py2gis-http --url http://127.0.0.1:8003/mcp
hermes mcp test py2gis-http
```

После подключения Hermes должен обнаружить ровно два инструмента. Пример
запроса модели:

> Проанализируй социальную и транспортную инфраструктуру в радиусе 5 км от
> точки 56.0678, 43.6031. Используй минимальный режим и верни по 5 ближайших
> объектов каждой категории. Отдельно укажи неполные категории.

## Использование из Python

```python
import asyncio

from py2gis_agents import DgisTools


async def main() -> None:
    async with DgisTools() as tools:
        result = await tools.analyze_social_infrastructure(
            latitude=56.0678,
            longitude=43.6031,
            radius_m=5000,
            mode="minimal",
            limit_per_category=5,
        )
        print(result.model_dump_json(indent=2))


asyncio.run(main())
```

## Семантика результата

- Объекты нормализованы и сгруппированы; сырые ответы 2GIS наружу не
  передаются.
- Дубликаты одного объекта внутри категории объединяются, а
  `matched_queries` показывает сработавшие формулировки.
- `source_complete=false` означает ошибку или внутреннее ограничение при
  загрузке исходных страниц.
- `response_limited=true` означает, что найдено больше объектов, чем разрешено
  вернуть параметром `limit_per_category`.
- `complete=true` только когда источник прочитан без известных ограничений и
  ответ не был сокращён.
- Расстояние является прямым расстоянием от заданной точки. Это не маршрут и
  не расстояние от границы земельного участка.

Внутренние защитные пределы: 10 объектов на страницу, 5 страниц на поисковую
формулировку, 100 объектов на формулировку и 1000 объектов на полный анализ.
Фактическая полнота также зависит от 2GIS, поисковой формулировки, доступных
рубрик, тарифных лимитов и актуальности данных провайдера.

## Разработка

```bash
python -m pip install -e '.[mcp]' --group test --group lint
pytest
ruff check .
mypy src
```

Документация провайдера: [2GIS Search API](https://docs.2gis.com/en/api/search/overview).
