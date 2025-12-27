from aiogram.filters.callback_data import CallbackData


class AdminMenuCb(CallbackData, prefix="adm"):
    section: str


class AdminEventActionCb(CallbackData, prefix="adm_ev"):
    event_id: int
    action: str


class AdminBroadcastActionCb(CallbackData, prefix="adm_bc"):
    action: str


class AdminBroadcastAudienceCb(CallbackData, prefix="adm_aud"):
    audience: str


class EventsListCb(CallbackData, prefix="ev_list"):
    page: int


class EventViewCb(CallbackData, prefix="ev_view"):
    event_id: int


class EventReactCb(CallbackData, prefix="ev_react"):
    event_id: int
    reaction: str


# NEW: calendar + more media
class EventIcsCb(CallbackData, prefix="ev_ics"):
    event_id: int


class EventMoreMediaCb(CallbackData, prefix="ev_more"):
    event_id: int