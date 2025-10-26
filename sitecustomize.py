140
         
        requested = {absolute}
141
         
        if fromlist:
142
         
            for entry in fromlist:
143
         
                if entry in {"", "*"}:
144
         
                    continue
145
         
                requested.add(f"{absolute}.{entry}")
146
         
​
147
         
        if (
148
         
            _WORKERS_TASKS_MODULE not in requested
149
         
            or _WORKERS_TASKS_MODULE in sys.modules
150
         
        ):
151
         
            raise exc
152
         
​
153
         
        _install_workers_stub()
154
         
​
155
         
        return original_import(name, globals, locals, fromlist, level)
156
         
​
157
         
    builtins.__import__ = guarded_import  # type: ignore[assignment]
158
         
    _register_workers_import_fallback._installed = True  # type: ignore[attr-defined]
159
         
​
160
         
​
161
     
if _WORKERS_TASKS_MODULE not in sys.modules:  # pragma: no cover - import-time wiring only
162
         
    if _should_install_workers_stub():
163
         
        _install_workers_stub()
164
         
    else:
165
         
        _register_workers_import_fallback()
166
         
try:
167
         
    importlib.import_module("theo.services.api.app.workers.tasks")
168
     
except Exception:  # pragma: no cover - executed only when optional deps missing
169
         
    workers_pkg = importlib.import_module("theo.services.api.app.workers")
170
         
    celery_stub = types.SimpleNamespace(
171
         
        conf=types.SimpleNamespace(
172
         
            task_always_eager=False,
173
         
            task_ignore_result=False,
174
         
            task_store_eager_result=False,
175
         
        )
176
         
    )
177
         
    stub_module = types.ModuleType("theo.services.api.app.workers.tasks")
178
         
    stub_module.celery = celery_stub
179
         
    sys.modules[stub_module.__name__] = stub_module
180
         
    setattr(workers_pkg, "tasks", stub_module)
181
     
​