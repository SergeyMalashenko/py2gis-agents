"""Infrastructure taxonomy used by the two public 2GIS tools."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import InfrastructureMode


@dataclass(frozen=True)
class InfrastructureCategory:
    """One output category and its 2GIS search/filter configuration."""

    group_key: str
    group_name: str
    key: str
    name: str
    minimal_queries: tuple[str, ...]
    extended_queries: tuple[str, ...]
    object_type: str | None = None
    rubric_terms: tuple[str, ...] = ()
    fallback_terms: tuple[str, ...] = ()
    disallowed_types: frozenset[str] = frozenset()
    accept_station_types: bool = False

    def queries(self, mode: InfrastructureMode) -> tuple[str, ...]:
        return self.minimal_queries if mode == "minimal" else self.extended_queries


SOCIAL_INFRASTRUCTURE_CATEGORIES: tuple[InfrastructureCategory, ...] = (
    InfrastructureCategory(
        "mandatory",
        "Обязательные услуги",
        "education",
        "Образование",
        ("школа",),
        (
            "школа",
            "детский сад",
            "колледж",
            "вуз",
            "дополнительное образование",
        ),
        rubric_terms=(
            "школ",
            "детск",
            "колледж",
            "университет",
            "вуз",
            "дополнительн",
        ),
        fallback_terms=(
            "школ",
            "детск",
            "колледж",
            "университет",
            "вуз",
        ),
    ),
    InfrastructureCategory(
        "mandatory",
        "Обязательные услуги",
        "healthcare",
        "Здравоохранение",
        ("медицинский центр",),
        (
            "больница",
            "поликлиника",
            "медицинский центр",
            "стоматология",
        ),
        rubric_terms=(
            "больниц",
            "поликлиник",
            "медицинск",
            "стоматолог",
        ),
        fallback_terms=(
            "больниц",
            "поликлиник",
            "медицинск",
            "стоматолог",
        ),
    ),
    InfrastructureCategory(
        "mandatory",
        "Обязательные услуги",
        "emergency_services",
        "Экстренные службы",
        ("экстренные службы",),
        (
            "пожарная часть",
            "полиция",
            "скорая медицинская помощь",
            "служба спасения",
        ),
        rubric_terms=(
            "пожарн",
            "полиц",
            "мвд",
            "скорая помощь",
            "служб спас",
            "мчс",
        ),
        fallback_terms=(
            "пожарн",
            "полиц",
            "мвд",
            "скорая помощь",
            "служб спас",
            "мчс",
        ),
    ),
    InfrastructureCategory(
        "everyday",
        "Повседневные услуги",
        "shops",
        "Магазины",
        ("продуктовый магазин",),
        (
            "продуктовый магазин",
            "супермаркет",
            "торговый центр",
        ),
        rubric_terms=(
            "продуктов",
            "супермаркет",
            "гипермаркет",
            "торговые центры",
            "универмаг",
        ),
        fallback_terms=(
            "продуктов",
            "супермаркет",
            "гипермаркет",
            "торговый центр",
            "универмаг",
        ),
    ),
    InfrastructureCategory(
        "everyday",
        "Повседневные услуги",
        "pharmacies",
        "Аптеки",
        ("аптека",),
        ("аптека",),
        rubric_terms=("аптек",),
        fallback_terms=("аптек",),
    ),
    InfrastructureCategory(
        "everyday",
        "Повседневные услуги",
        "banks",
        "Банки",
        ("банк",),
        ("банк", "банкомат"),
        rubric_terms=("банк", "банкомат"),
        fallback_terms=("банк", "банкомат"),
    ),
    InfrastructureCategory(
        "everyday",
        "Повседневные услуги",
        "post",
        "Почта",
        ("почтовое отделение",),
        ("почтовое отделение",),
        rubric_terms=("почт",),
        fallback_terms=("почт",),
    ),
    InfrastructureCategory(
        "everyday",
        "Повседневные услуги",
        "government_services",
        "Государственные услуги",
        ("МФЦ",),
        ("МФЦ", "администрация", "налоговая инспекция"),
        rubric_terms=(
            "мфц",
            "администрац",
            "федеральн",
            "государственн",
            "налогов",
        ),
        fallback_terms=("мфц", "администрац", "налогов"),
    ),
    InfrastructureCategory(
        "leisure",
        "Досуг и качество среды",
        "sports",
        "Спортивные объекты",
        ("спортивный комплекс",),
        (
            "спортивный комплекс",
            "стадион",
            "бассейн",
            "фитнес-клуб",
        ),
        rubric_terms=(
            "спорт",
            "стадион",
            "бассейн",
            "фитнес",
            "тренажерн",
            "йог",
            "картинг",
        ),
        fallback_terms=("спорт", "стадион", "бассейн", "фитнес"),
    ),
    InfrastructureCategory(
        "leisure",
        "Досуг и качество среды",
        "culture",
        "Учреждения культуры",
        ("дом культуры",),
        ("дом культуры", "библиотека", "музей", "театр"),
        rubric_terms=(
            "дом культуры",
            "дома культуры",
            "библиотек",
            "музе",
            "театр",
        ),
        fallback_terms=("дом культуры", "библиотек", "музе", "театр"),
    ),
    InfrastructureCategory(
        "leisure",
        "Досуг и качество среды",
        "parks",
        "Парки и зоны отдыха",
        ("парк",),
        ("парк", "сквер", "зона отдыха"),
        rubric_terms=("парк", "сквер", "баз", "пляж", "зон отдыха"),
        fallback_terms=("парк", "сквер", "баз", "зон отдыха", "пляж"),
    ),
)


TRANSPORT_INFRASTRUCTURE_CATEGORIES: tuple[InfrastructureCategory, ...] = (
    InfrastructureCategory(
        "public_transport",
        "Общественный транспорт",
        "public_transport_stops",
        "Остановки",
        ("остановка общественного транспорта",),
        ("остановка общественного транспорта",),
        object_type="station",
        rubric_terms=(
            "останов",
            "общественн транспорт",
            "автобус",
            "трамва",
            "троллейбус",
        ),
        fallback_terms=("останов", "bus", "tram", "trolleybus", "shuttle_bus"),
        accept_station_types=True,
    ),
    InfrastructureCategory(
        "public_transport",
        "Общественный транспорт",
        "railway_stations_platforms",
        "Железнодорожные станции и платформы",
        ("железнодорожная станция",),
        (
            "железнодорожная станция",
            "железнодорожная платформа",
            "вокзал",
        ),
        object_type="station,station_platform",
        rubric_terms=(
            "железнодорож",
            "вокзал",
            "станци",
            "платформ",
        ),
        fallback_terms=(
            "железнодорож",
            "вокзал",
            "станци",
            "платформ",
            "rail",
            "train",
        ),
        accept_station_types=True,
    ),
    InfrastructureCategory(
        "public_transport",
        "Общественный транспорт",
        "bus_stations",
        "Автовокзалы и автостанции",
        ("автостанция",),
        ("автостанция", "автовокзал"),
        object_type="station,branch",
        rubric_terms=("автовокзал", "автостанц"),
        fallback_terms=("автовокзал", "автостанц", "bus_station"),
        accept_station_types=True,
    ),
    InfrastructureCategory(
        "transport_hubs",
        "Транспортные узлы",
        "railway_objects",
        "Железнодорожные объекты",
        ("железнодорожный вокзал",),
        (
            "железнодорожный вокзал",
            "железнодорожное депо",
            "грузовая станция",
        ),
        object_type="station,station_platform,branch",
        rubric_terms=(
            "железнодорож",
            "вокзал",
            "депо",
            "грузов станц",
        ),
        fallback_terms=(
            "железнодорож",
            "вокзал",
            "депо",
            "грузов станц",
        ),
        accept_station_types=True,
    ),
    InfrastructureCategory(
        "transport_hubs",
        "Транспортные узлы",
        "airports",
        "Аэропорты",
        ("аэропорт",),
        ("аэропорт", "аэродром"),
        rubric_terms=("аэропорт", "аэродром"),
        fallback_terms=("аэропорт", "аэродром", "airport"),
        disallowed_types=frozenset({"station", "station_platform", "route"}),
    ),
    InfrastructureCategory(
        "transport_hubs",
        "Транспортные узлы",
        "ports",
        "Порты",
        ("порт",),
        ("порт", "речной порт", "речной вокзал"),
        rubric_terms=("порт", "речной вокзал"),
        fallback_terms=("порт", "речной вокзал", "harbour", "harbor"),
        disallowed_types=frozenset({"station", "station_platform", "route"}),
    ),
    InfrastructureCategory(
        "transport_hubs",
        "Транспортные узлы",
        "logistics_terminals",
        "Логистические терминалы",
        ("логистический терминал",),
        (
            "логистический терминал",
            "логистический комплекс",
            "грузовой терминал",
        ),
        rubric_terms=(
            "логист",
            "грузов терминал",
            "транспортн терминал",
            "складск",
            "контейнерн терминал",
        ),
        fallback_terms=(
            "логист",
            "грузов терминал",
            "транспортн терминал",
            "складск",
            "контейнерн терминал",
        ),
        disallowed_types=frozenset({"station", "station_platform", "route"}),
    ),
)
