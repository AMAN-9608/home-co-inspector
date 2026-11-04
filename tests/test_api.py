from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from secondinspector import api


def test_structured_request_can_route_second_look_to_wonder():
    # Arrange
    create = Mock(return_value=SimpleNamespace(status='completed', output_text='{"candidates": []}'))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    content = [{'type': 'input_video', 'file_id': 'file-1'}]
    schema = {'type': 'object'}

    # Act
    result = api.spark_json(client, content, schema, 'unspoken_candidates', model='muse-wonder-1.0')

    # Assert
    assert result == {'candidates': []}
    assert create.call_args.kwargs['model'] == 'muse-wonder-1.0'
    assert create.call_args.kwargs['input'][0]['content'] == content
    assert create.call_args.kwargs['text']['format']['strict'] is True


def test_narration_and_evidence_requests_still_default_to_spark():
    # Arrange
    create = Mock(return_value=SimpleNamespace(status='completed', output_text='{}'))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))

    # Act
    api.spark_json(client, [], {}, 'evidence_check')

    # Assert
    assert create.call_args.kwargs['model'] == 'muse-spark-1.3'


def test_incomplete_wonder_response_identifies_model():
    # Arrange
    client = SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=SimpleNamespace(status='incomplete'))))

    # Act and assert
    with pytest.raises(RuntimeError, match='muse-wonder-1.0 returned incomplete'):
        api.spark_json(client, [], {}, 'unspoken_candidates', model='muse-wonder-1.0')
