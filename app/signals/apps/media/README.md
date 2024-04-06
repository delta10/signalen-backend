# Protected media

This app provides the possibility to protect the media folder. To use this functionality in production, specific uWSGI settings are required to use the X-Sendfile header.

You can run uWSGI as follows:

```bash
uwsgi \
    --master \
    --http=0.0.0.0:8000 \
    --module=signals.wsgi:application \
    --static-map=/signals/static=./app/static \
    --static-safe=./app/media \
    --plugins=router_static \
    --offload-threads=2 \
    --collect-header="X-Sendfile X_SENDFILE" \
    --response-route-if-not="empty:${X_SENDFILE} static:${X_SENDFILE}" \
    --buffer-size=32768 \
    --py-auto-reload=1 \
    --die-on-term
```

The relevant settings are `plugins`, `offload-threads`, `collect-header` and `response-route-if-not`. For more information see the [X-Sendfile emulation snippet of the uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/Snippets.html#x-sendfile-emulation).