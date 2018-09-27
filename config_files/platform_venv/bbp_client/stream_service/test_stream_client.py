# pylint: disable=C0111
from bbp_client.stream_service.client import Client

from nose.tools import eq_
from mock import patch, Mock, ANY


class TestStreamClient(object):
    def setUp(self):
        self.mock_oidc = Mock()
        self.stream = Client('api/', self.mock_oidc)

    def test_register_activity(self):
        with patch('bbp_client.stream_service.client.requests') as mock_req:
            mock_req.post.return_value = resp = Mock()
            resp.status_code = 201

            self.stream.register_activity({'actor': {'id': 'actor'}})
            mock_req.post.assert_called_once_with('api/activity/', json={'actor': {'id': 'actor'},
                                                                         'references': {},
                                                                         'time': ANY},
                                                  headers=ANY)

    def test_send_notification(self):
        with patch('bbp_client.stream_service.client.requests') as mock_req:
            mock_req.post.return_value = resp = Mock()
            resp.status_code = 201

            self.stream.send_notification({'summary': 'notification'})
            mock_req.post.assert_called_once_with('api/notification/',
                                                  json={'summary': 'notification'},
                                                  headers=ANY)

    def test_inidces(self):
        with patch('bbp_client.stream_service.client.requests') as mock_req:
            mock_req.post.return_value = resp = Mock()
            resp.status_code = 201

            actor_name = 'aname asurname'
            summary = 'actor %s did something' % actor_name
            activity = {'actor': {'id': 'aid', 'type': 'atype', 'name': actor_name},
                        'summary': summary}

            self.stream.register_activity(activity)
            posted_json = mock_req.post.call_args[1]['json']
            eq_(posted_json['references']['actor']['indices'],
                [summary.index(actor_name), summary.index(actor_name) + len(actor_name)])
