import asyncio
from time import time

from operator_db.connection.main import get_async_engine, get_sessionmaker, with_session
from operator_db.objects import SessionAgentSvc
from operator_db.objects.session import SessionSvc
from operator_shared.printing import p, pp
from operator_shared.settings import load_operator_settings
from operator_shared.utils import remove_empty, walk_dicts


async def _main() -> None:
    settings = load_operator_settings()
    engine = get_async_engine(settings)
    sessionmaker = get_sessionmaker(engine)
    async with with_session(sessionmaker) as s:
        svc = SessionSvc(
            settings=settings,
            session=s,
        )
        ag_svc = SessionAgentSvc(
            settings=settings,
            session=s,
        )
        session_obj = await svc.make_session(
            session_title="My first section",
            with_orchestrator=True,
        )
        orch_ag = await session_obj.get_orchestrator(s)
        last_ev = await ag_svc.get_last_event(agent=orch_ag)
        if not last_ev:
            msg = "Session somehow has no events!"
            raise ValueError(msg)

        ctx_id = last_ev.context_id

        num_msg = 50
        t_0 = time()
        for i in range(num_msg):
            last_ev = await ag_svc.add_message(
                parent_id=last_ev.id,
                context_id=ctx_id,
                text_data=f"Salve {i}",
            )
        t_f = time()
        t_d = t_f - t_0

        d = await session_obj.as_dict()
        d = walk_dicts(d, predicate=remove_empty)

        pp(d)
        p(f"Took {t_d:.4f}s on {num_msg} reqs - avg: {(t_d / num_msg):.4f}s/req")


if __name__ == "__main__":
    asyncio.run(_main())
