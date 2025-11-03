from unittest.mock import Mock, call

from theo.adapters import AdapterRegistry
from theo.application.services.bootstrap import bootstrap_application


def test_bootstrap_application_invokes_factories_once():
    registry = AdapterRegistry()

    ingest_callable = Mock(name="ingest")
    retire_callable = Mock(name="retire")
    get_callable = Mock(name="get")
    list_callable = Mock(name="list", return_value=["doc"])
    research_service = Mock(name="research_service", return_value="service")

    command_factory = Mock(return_value=ingest_callable)
    retire_factory = Mock(return_value=retire_callable)
    get_factory = Mock(return_value=get_callable)
    list_factory = Mock(return_value=list_callable)
    research_factory = Mock(return_value=research_service)

    container = bootstrap_application(
        registry=registry,
        command_factory=command_factory,
        retire_factory=retire_factory,
        get_factory=get_factory,
        list_factory=list_factory,
        research_factory=research_factory,
    )

    command_factory.assert_called_once_with()
    retire_factory.assert_called_once_with()
    get_factory.assert_called_once_with()
    list_factory.assert_called_once_with()
    research_factory.assert_called_once_with()

    assert container.bind_command() is ingest_callable
    assert container.bind_retire() is retire_callable
    assert container.bind_get() is get_callable

    list_adapter = container.bind_list()
    assert list_adapter() == ["doc"]
    assert list_adapter(7) == ["doc"]
    assert list_callable.call_args_list == [call(limit=20), call(limit=7)]

    session = object()
    assert container.get_research_service(session) == "service"
    research_service.assert_called_once_with(session)
