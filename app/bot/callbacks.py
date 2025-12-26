from aiogram.filters.callback_data import CallbackData


class EventsListCb(CallbackData, prefix="evl"):
    page: int


class EventViewCb(CallbackData, prefix="evv"):
    event_id: int


class EventReactCb(CallbackData, prefix="evr"):
    event_id: int
    reaction: str  # "interested" | "declined"


class AdminMenuCb(CallbackData, prefix="adm"):
    section: str  # "events" | "broadcasts" | "stats"


class AdminEventActionCb(CallbackData, prefix="aea"):
    event_id: int
    action: str  # "view" | "edit" | "delete" | "publish" | "archive" | "report"


class AdminBroadcastActionCb(CallbackData, prefix="aba"):
    action: str  # "new" | "run" | "list"
    broadcast_id: int | None = None


class AdminBroadcastAudienceCb(CallbackData, prefix="aud"):
    audience: str  # "all" | "subscribed" | "active" | "no_response" | "ever_interested"


class AdminBroadcastPickEventCb(CallbackData, prefix="bpe"):
    event_id: int

from aiogram.filters.callback_data import CallbackData


class EventsListCb(CallbackData, prefix="evl"):
    page: int


class EventViewCb(CallbackData, prefix="evv"):
    event_id: int


class EventReactCb(CallbackData, prefix="evr"):
    event_id: int
    reaction: str  # interested / declined


class EventIcsCb(CallbackData, prefix="evics"):
    event_id: int