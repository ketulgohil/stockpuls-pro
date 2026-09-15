from fastapi import APIRouter

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("")
def list_strategies():
    from core.screener_strategies import get_all_strategies
    return get_all_strategies()


@router.get("/{strategy_key}")
def run_strategy(strategy_key: str):
    from core.screener_strategies import run_strategy
    results = run_strategy(strategy_key)
    return {"strategy": strategy_key, "results": results, "count": len(results)}
