from datetime import datetime, timedelta
from sanic_session.base import BaseSessionInterface
import warnings


class MongoDBSessionInterface(BaseSessionInterface):
    expiry_field = 'expiry'
    sid_field = 'sid'
    data_field = 'data'

    def __init__(
            self, app, coll: str = 'session',
            domain: str = None,
            expiry: int = 30 * 24 * 60 * 60,
            httponly: bool = True,
            cookie_name: str = 'session',
            sessioncookie: bool = False,
            samesite: str = None,
            session_name: str = 'session'):
        """Initializes the interface for storing client sessions in MongoDB.

        Args:
            app (sanic.Sanic):
                Sanic instance to register listener('after_server_start')
            coll (str, optional):
                MongoDB collection name for session
            domain (str, optional):
                Optional domain which will be attached to the cookie.
            expiry (int, optional):
                Seconds until the session should expire.
            httponly (bool, optional):
                Adds the `httponly` flag to the session cookie.
            cookie_name (str, optional):
                Name used for the client cookie.
            sessioncookie (bool, optional):
                Specifies if the sent cookie should be a 'session cookie', i.e
                no Expires or Max-age headers are included. Expiry is still
                fully tracked on the server side. Default setting is False.
            samesite (str, optional):
                Will prevent the cookie from being sent by the browser to
                the target site in all cross-site browsing context, even when
                following a regular link.
                One of ('lax', 'strict')
                Default: None
            session_name (str, optional):
                Name of the session that will be accessible through the
                request.
                e.g. If ``session_name`` is ``alt_session``, it should be
                accessed like that: ``request['alt_session']``
                e.g. And if ``session_name`` is left to default, it should be
                accessed like that: ``request['session']``
                Default: 'session'
        """
        try:
            from sanic_motor import BaseModel
        except ImportError:  # pragma: no cover
            raise RuntimeError("Please install Mongo dependencies: "
                               "pip install sanic_session[mongo]")

        class _SessionModel(BaseModel):
            __coll__ = coll
            """Collection for session storing.

            Collection name (default session)

            Fields:
                sid
                expiry
                data:
                    User's session data
            """
            pass

        # prefix not needed for mongodb as mongodb uses uuid4 natively
        prefix = ''

        if httponly is not True:
            warnings.warn('''
                httponly default arg has changed.
                To spare you some debugging time, httponly is currently
                hardcoded as True. This message will be removed with the
                next release. And ``httponly`` will no longer be hardcoded
            ''', DeprecationWarning)

        super().__init__(
            expiry=expiry,
            prefix=prefix,
            cookie_name=cookie_name,
            domain=domain,
            # I'm gonna leave this as True because changing it might
            # be hazardous. But this should be changed to __init__'s
            # httponly kwarg instead of being hardcoded
            httponly=True,
            sessioncookie=sessioncookie,
            samesite=samesite,
            session_name=session_name,
        )

        # set collection name
        self.SessionModel = _SessionModel

        @app.listener('after_server_start')
        async def apply_session_indexes(app, loop):
            """Create indexes in session collection
            if doesn't exist.

            Indexes:
                sid:
                    For faster lookup.
                expiry:
                    For document expiration.
            """
            await _SessionModel.create_index(self.sid_field)
            await _SessionModel.create_index(self.expiry_field, expireAfterSeconds=0)

    async def _get_value(self, prefix, key):
        value = await self.SessionModel.find_one({self.sid_field: key}, as_raw=True)
        return value.get(self.data_field) if value else None

    async def _delete_key(self, key):
        await self.SessionModel.delete_one({self.sid_field: key})

    async def _set_value(self, key, data):
        expiry = datetime.utcnow() + timedelta(seconds=self.expiry)
        await self.SessionModel.replace_one(
            {self.sid_field: key},
            {
                self.sid_field: key,
                self.expiry_field: expiry,
                self.data_field: data
            },
            upsert=True
        )
