from market_data_downloader.models import IndexCategory, IndexInstrument


def _build_catalog(
    category: IndexCategory,
    entries: tuple[tuple[str, str, str], ...],
) -> tuple[IndexInstrument, ...]:
    return tuple(
        IndexInstrument(
            name=name,
            instrument_key=f"NSE_INDEX|{key}",
            category=category,
            slug=slug,
        )
        for name, key, slug in entries
    )


BROAD_INDICES = _build_catalog(
    IndexCategory.BROAD,
    (
        ("Nifty 50", "Nifty 50", "nifty50"),
        ("Nifty Next 50", "Nifty Next 50", "nifty-next-50"),
        ("Nifty 100", "Nifty 100", "nifty-100"),
        ("Nifty 200", "Nifty 200", "nifty-200"),
        ("Nifty 500", "Nifty 500", "nifty-500"),
        ("Nifty Midcap 50", "Nifty Midcap 50", "nifty-midcap-50"),
        ("Nifty Midcap 100", "NIFTY MIDCAP 100", "nifty-midcap-100"),
        ("Nifty Midcap 150", "NIFTY MIDCAP 150", "nifty-midcap-150"),
        ("Nifty Smallcap 50", "NIFTY SMLCAP 50", "nifty-smallcap-50"),
        ("Nifty Smallcap 100", "NIFTY SMLCAP 100", "nifty-smallcap-100"),
        ("Nifty Smallcap 250", "NIFTY SMLCAP 250", "nifty-smallcap-250"),
        ("Nifty LargeMidcap 250", "NIFTY LARGEMID250", "nifty-largemidcap-250"),
        ("Nifty MidSmallcap 400", "NIFTY MIDSML 400", "nifty-midsmallcap-400"),
        ("Nifty Microcap 250", "NIFTY MICROCAP250", "nifty-microcap-250"),
        ("Nifty Total Market", "NIFTY TOTAL MKT", "nifty-total-market"),
        ("Nifty 500 Multicap", "NIFTY500 MULTICAP", "nifty-500-multicap"),
        ("Nifty Mid Select", "NIFTY MID SELECT", "nifty-mid-select"),
    ),
)

SECTORAL_INDICES = _build_catalog(
    IndexCategory.SECTORAL,
    (
        ("Nifty Auto", "Nifty Auto", "nifty-auto"),
        ("Nifty Bank", "Nifty Bank", "nifty-bank"),
        ("Nifty Financial Services", "Nifty Fin Service", "nifty-financial-services"),
        (
            "Nifty Financial Services 25/50",
            "Nifty FinSrv25 50",
            "nifty-financial-services-25-50",
        ),
        (
            "Nifty Financial Services Ex-Bank",
            "Nifty FinSerExBnk",
            "nifty-financial-services-ex-bank",
        ),
        ("Nifty FMCG", "Nifty FMCG", "nifty-fmcg"),
        ("Nifty IT", "Nifty IT", "nifty-it"),
        ("Nifty Media", "Nifty Media", "nifty-media"),
        ("Nifty Metal", "Nifty Metal", "nifty-metal"),
        ("Nifty Pharma", "Nifty Pharma", "nifty-pharma"),
        ("Nifty PSU Bank", "Nifty PSU Bank", "nifty-psu-bank"),
        ("Nifty Private Bank", "Nifty Pvt Bank", "nifty-private-bank"),
        ("Nifty Realty", "Nifty Realty", "nifty-realty"),
        ("Nifty Healthcare", "NIFTY HEALTHCARE", "nifty-healthcare"),
        (
            "Nifty Consumer Durables",
            "NIFTY CONSR DURBL",
            "nifty-consumer-durables",
        ),
        ("Nifty Oil & Gas", "NIFTY OIL AND GAS", "nifty-oil-and-gas"),
        ("Nifty Chemicals", "Nifty Chemicals", "nifty-chemicals"),
        ("Nifty Cement", "Nifty Cement", "nifty-cement"),
        ("Nifty Energy", "Nifty Energy", "nifty-energy"),
        ("Nifty Infrastructure", "Nifty Infra", "nifty-infrastructure"),
        ("Nifty Services Sector", "Nifty Serv Sector", "nifty-services-sector"),
    ),
)

ALL_INDICES = BROAD_INDICES + SECTORAL_INDICES

if len({index.instrument_key for index in ALL_INDICES}) != len(ALL_INDICES):
    raise RuntimeError("Index catalog contains duplicate instrument keys.")

if len({(index.category, index.slug) for index in ALL_INDICES}) != len(ALL_INDICES):
    raise RuntimeError("Index catalog contains duplicate output folders.")
