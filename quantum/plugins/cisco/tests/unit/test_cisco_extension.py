# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @authors: Shweta Padubidri, Cisco Systems, Inc.
#           Peter Strunk , Cisco Systems, Inc.
#           Shubhangi Satras , Cisco Systems, Inc.
import unittest
import logging
import webob
import json
import os.path
import routes
from webtest import TestApp
from extensions import credential
from extensions import portprofile
from extensions import novatenant
from extensions import qos
from quantum.plugins.cisco.db import api as db
from quantum.common import wsgi
from quantum.common import config
from quantum.common import extensions
from quantum import api as server
from quantum.plugins.cisco.l2network_plugin import L2Network
from tests.unit.extension_stubs import StubBaseAppController
from quantum.common.extensions import (PluginAwareExtensionManager,
                                       ExtensionMiddleware)
from quantum.manager import QuantumManager
from quantum.plugins.cisco import l2network_plugin

TEST_CONF_FILE = os.path.join(os.path.dirname(__file__), os.pardir,
                              os.pardir, 'conf', 'quantum.conf.ciscoext')
EXTENSIONS_PATH = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                               os.pardir, os.pardir, os.pardir, "extensions")

LOG = logging.getLogger('quantum.plugins.cisco.tests.test_cisco_extensions')


class ExtensionsTestApp(wsgi.Router):

    def __init__(self, options=None):
        options = options or {}
        mapper = routes.Mapper()
        controller = StubBaseAppController()
        mapper.resource("dummy_resource", "/dummy_resources",
                        controller=controller)
        super(ExtensionsTestApp, self).__init__(mapper)


class PortprofileExtensionTest(unittest.TestCase):

    def setUp(self):

        """ Set up function """

        parent_resource = dict(member_name="tenant",
                               collection_name="extensions/csco/tenants")
        member_actions = {'associate_portprofile': "PUT",
                          'disassociate_portprofile': "PUT"}
        controller = portprofile.PortprofilesController(
                               QuantumManager.get_plugin())
        res_ext = extensions.ResourceExtension('portprofiles', controller,
                                             parent=parent_resource,
                                             member_actions=member_actions)
        self.test_app = setup_extensions_test_app(
                                          SimpleExtensionManager(res_ext))
        self.contenttype = 'application/json'
        self.profile_path = '/extensions/csco/tenants/tt/portprofiles'
        self.portprofile_path = '/extensions/csco/tenants/tt/portprofiles/'
        self.test_port_profile = {'portprofile':
                                 {'portprofile_name': 'cisco_test_portprofile',
                                 'qos_name': 'test-qos1'}}
        self.tenant_id = "test_tenant"
        self.network_name = "test_network"
        options = {}
        options['plugin_provider'] = 'quantum.plugins.cisco.l2network_plugin'\
                                     '.L2Network'
        self.api = server.APIRouterV01(options)
        self._l2network_plugin = l2network_plugin.L2Network()

    def test_list_portprofile(self):

        """ Test List Portprofile"""

        LOG.debug("test_list_portprofile - START")
        req_body1 = json.dumps(self.test_port_profile)
        create_response1 = self.test_app.post(
                           self.profile_path, req_body1,
                           content_type=self.contenttype)
        req_body2 = json.dumps({'portprofile':
                               {'portprofile_name': 'cisco_test_portprofile2',
                                'qos_name': 'test-qos2'}})
        create_response2 = self.test_app.post(
                                self.profile_path, req_body2,
                                content_type=self.contenttype)

        index_response = self.test_app.get(self.profile_path)
        self.assertEqual(200, index_response.status_int)

        # Clean Up - Delete the Port Profiles
        resp_body1 = wsgi.Serializer().deserialize(create_response1.body,
                                                   self.contenttype)
        portprofile_path1_temp = self.portprofile_path +\
                              resp_body1['portprofiles']['portprofile']['id']
        portprofile_path1 = str(portprofile_path1_temp)
        resp_body2 = wsgi.Serializer().deserialize(create_response2.body,
                                                   self.contenttype)
        portprofile_path2_temp = self.portprofile_path +\
                              resp_body2['portprofiles']['portprofile']['id']
        portprofile_path2 = str(portprofile_path2_temp)
        self.tear_down_profile(portprofile_path1)
        self.tear_down_profile(portprofile_path2)
        LOG.debug("test_list_portprofile - END")

    def test_create_portprofile(self):

        """ Test create Portprofile"""

        LOG.debug("test_create_portprofile - START")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(self.profile_path, req_body,
                                            content_type=self.contenttype)
        self.assertEqual(200, index_response.status_int)

        # Clean Up - Delete the Port Profile
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        portprofile_path_temp = self.portprofile_path +\
                              resp_body['portprofiles']['portprofile']['id']
        portprofile_path = str(portprofile_path_temp)
        self.tear_down_profile(portprofile_path)
        LOG.debug("test_create_portprofile - END")

    def test_create_portprofileBADRequest(self):

        """ Test create Portprofile Bad Request"""

        LOG.debug("test_create_portprofileBADRequest - START")
        index_response = self.test_app.post(self.profile_path, 'BAD_REQUEST',
                                            content_type=self.contenttype,
                                            status='*')
        self.assertEqual(400, index_response.status_int)
        LOG.debug("test_create_portprofileBADRequest - END")

    def test_show_portprofile(self):

        """ Test show Portprofile """

        LOG.debug("test_show_portprofile - START")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(self.profile_path, req_body,
                                            content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        show_path_temp = self.portprofile_path +\
                            resp_body['portprofiles']['portprofile']['id']
        show_port_path = str(show_path_temp)
        show_response = self.test_app.get(show_port_path)
        self.assertEqual(200, show_response.status_int)

        # Clean Up - Delete the Port Profile
        self.tear_down_profile(show_port_path)
        LOG.debug("test_show_portprofile - END")

    def test_show_portprofileDNE(self, portprofile_id='100'):

        """ Test show Portprofile does not exist"""

        LOG.debug("test_show_portprofileDNE - START")
        show_path_temp = self.portprofile_path + portprofile_id
        show_port_path = str(show_path_temp)
        show_response = self.test_app.get(show_port_path, status='*')
        self.assertEqual(450, show_response.status_int)
        LOG.debug("test_show_portprofileDNE - END")

    def test_update_portprofile(self):

        """ Test update Portprofile"""

        LOG.debug("test_update_portprofile - START")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(
                         self.profile_path, req_body,
                         content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        rename_port_profile = {'portprofile':
                              {'portprofile_name': 'cisco_rename_portprofile',
                              'qos_name': 'test-qos1'}}
        rename_req_body = json.dumps(rename_port_profile)
        rename_path_temp = self.portprofile_path +\
                                resp_body['portprofiles']['portprofile']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, rename_req_body)
        self.assertEqual(200, rename_response.status_int)

        # Clean Up - Delete the Port Profile
        self.tear_down_profile(rename_path)
        LOG.debug("test_update_portprofile - END")

    def test_update_portprofileBADRequest(self):

        """ Test update Portprofile Bad Request"""

        LOG.debug("test_update_portprofileBADRequest - START")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(
                         self.profile_path, req_body,
                         content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        rename_path_temp = self.portprofile_path +\
                                resp_body['portprofiles']['portprofile']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, 'BAD_REQUEST',
                                            status='*')
        self.assertEqual(400, rename_response.status_int)

        # Clean Up - Delete the Port Profile
        self.tear_down_profile(rename_path)
        LOG.debug("test_update_portprofileBADRequest - END")

    def test_update_portprofileDNE(self, portprofile_id='100'):

        """ Test update Portprofile does not exist"""

        LOG.debug("test_update_portprofileiDNE - START")
        rename_port_profile = {'portprofile':
                              {'portprofile_name': 'cisco_rename_portprofile',
                              'qos_name': 'test-qos1'}}
        rename_req_body = json.dumps(rename_port_profile)
        update_path_temp = self.portprofile_path + portprofile_id
        update_path = str(update_path_temp)
        update_response = self.test_app.put(update_path, rename_req_body,
                                            status='*')
        self.assertEqual(450, update_response.status_int)
        LOG.debug("test_update_portprofileDNE - START")

    def test_delete_portprofile(self):

        """ Test delete Portprofile"""

        LOG.debug("test_delete_portprofile - START")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(
                              self.profile_path, req_body,
                              content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        delete_path_temp = self.portprofile_path +\
                                resp_body['portprofiles']['portprofile']['id']
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path)

        self.assertEqual(202, delete_response.status_int)
        LOG.debug("test_delete_portprofile - END")

    def test_delete_portprofileDNE(self, portprofile_id='100'):

        """ Test delete Portprofile does not exist"""

        LOG.debug("test_delete_portprofileDNE - START")
        delete_path_temp = self.portprofile_path + portprofile_id
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path, status='*')
        self.assertEqual(450, delete_response.status_int)
        LOG.debug("test_delete_portprofileDNE - END")

    def create_request(self, path, body, content_type, method='GET'):

        """ Test create request"""

        LOG.debug("test_create_request - START")
        req = webob.Request.blank(path)
        req.method = method
        req.headers = {}
        req.headers['Accept'] = content_type
        req.body = body
        return req
        LOG.debug("test_create_request - END")

    def _create_network(self, name=None):

        """ Test create network"""

        LOG.debug("Creating network - START")
        if name:
            net_name = name
        else:
            net_name = self.network_name
        net_path = "/tenants/tt/networks"
        net_data = {'network': {'net-name': '%s' % net_name}}
        req_body = wsgi.Serializer().serialize(net_data, self.contenttype)
        network_req = self.create_request(net_path, req_body,
                                          self.contenttype, 'POST')
        network_res = network_req.get_response(self.api)
        network_data = wsgi.Serializer().deserialize(network_res.body,
                                                     self.contenttype)
        return network_data['networks']['network']['id']
        LOG.debug("Creating network - END")

    def _create_port(self, network_id, port_state):

        """ Test create port"""

        LOG.debug("Creating port for network %s - START", network_id)
        port_path = "/tenants/tt/networks/%s/ports" % network_id
        port_req_data = {'port': {'port-state': '%s' % port_state}}
        req_body = wsgi.Serializer().serialize(port_req_data,
                                               self.contenttype)
        port_req = self.create_request(port_path, req_body,
                                       self.contenttype, 'POST')
        port_res = port_req.get_response(self.api)
        port_data = wsgi.Serializer().deserialize(port_res.body,
                                                  self.contenttype)
        return port_data['ports']['port']['id']
        LOG.debug("Creating port for network - END")

    def test_associate_portprofile(self):

        """ Test associate portprofile"""

        LOG.debug("test_associate_portprofile - START")
        net_id = self._create_network()
        port_id = self._create_port(net_id, "ACTIVE")
        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(
                              self.profile_path, req_body,
                              content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        test_port_assign_data = {'portprofile': {'network-id': net_id,
                                         'port-id': port_id}}
        req_assign_body = json.dumps(test_port_assign_data)
        associate_path_temp = self.portprofile_path +\
                         resp_body['portprofiles']['portprofile']['id'] +\
                         "/associate_portprofile"
        associate_path = str(associate_path_temp)
        associate_response = self.test_app.put(
                                  associate_path, req_assign_body,
                                  content_type=self.contenttype)
        self.assertEqual(202, associate_response.status_int)

        # Clean Up - Disassociate and Delete the Port Profile
        disassociate_path_temp = self.portprofile_path +\
                            resp_body['portprofiles']['portprofile']['id'] +\
                            "/disassociate_portprofile"
        disassociate_path = str(disassociate_path_temp)
        delete_path_temp = self.portprofile_path +\
                                resp_body['portprofiles']['portprofile']['id']
        delete_path = str(delete_path_temp)
        self.tear_down_associate_profile(delete_path, disassociate_path,
                                      req_assign_body)
        LOG.debug("test_associate_portprofile - END")

    def test_associate_portprofileDNE(self, portprofile_id='100'):

        """ Test associate portprofile does not exist"""

        LOG.debug("test_associate_portprofileDNE - START")
        test_port_assign_data = {'portprofile': {'network-id': '001',
                                         'port-id': '1'}}
        req_assign_body = json.dumps(test_port_assign_data)
        associate_path = self.portprofile_path + portprofile_id +\
                         "/associate_portprofile"
        associate_response = self.test_app.put(
                              associate_path, req_assign_body,
                              content_type=self.contenttype, status='*')
        self.assertEqual(450, associate_response.status_int)
        LOG.debug("test_associate_portprofileDNE - END")

    def test_disassociate_portprofile(self):

        """ Test disassociate portprofile"""

        LOG.debug("test_disassociate_portprofile - START")
        net_id = self._create_network()
        port_id = self._create_port(net_id, "ACTIVE")

        req_body = json.dumps(self.test_port_profile)
        index_response = self.test_app.post(
                              self.profile_path, req_body,
                              content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)

        test_port_assign_data = {'portprofile': {'network-id': net_id,
                                         'port-id': port_id}}
        req_assign_body = json.dumps(test_port_assign_data)
        associate_path_temp = self.portprofile_path +\
                              resp_body['portprofiles']['portprofile']['id'] +\
                              "/associate_portprofile"
        associate_path = str(associate_path_temp)
        self.test_app.put(associate_path, req_assign_body,
                                               content_type=self.contenttype)
        disassociate_path_temp = self.portprofile_path +\
                            resp_body['portprofiles']['portprofile']['id'] +\
                            "/disassociate_portprofile"

        disassociate_path = str(disassociate_path_temp)
        disassociate_response = self.test_app.put(
                                     disassociate_path, req_assign_body,
                                     content_type=self.contenttype)
        self.assertEqual(202, disassociate_response.status_int)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        delete_path_temp = self.portprofile_path +\
                                resp_body['portprofiles']['portprofile']['id']
        delete_path = str(delete_path_temp)
        self.tear_down_profile(delete_path)
        LOG.debug("test_disassociate_portprofile - END")

    def tear_down_profile(self, delete_profile_path):

        """ Tear down profile"""

        self.test_app.delete(delete_profile_path)

    def tear_down_associate_profile(self, delete_profile_path,
                                 dissociate_profile_path, req_body):

        """ Tear down associate profile"""

        self.test_app.put(dissociate_profile_path, req_body,
                           content_type=self.contenttype)
        self.tear_down_profile(delete_profile_path)

    def tearDown(self):

        """ Tear down """

        db.clear_db()


class NovatenantExtensionTest(unittest.TestCase):

    def setUp(self):

        """ Set up function"""

        parent_resource = dict(member_name="tenant",
                               collection_name="extensions/csco/tenants")
        member_actions = {'get_host': "PUT",
                          'get_instance_port': "PUT"}
        controller = novatenant.NovatenantsController(
                               QuantumManager.get_plugin())
        res_ext = extensions.ResourceExtension('novatenants', controller,
                                             parent=parent_resource,
                                             member_actions=member_actions)
        self.test_app = setup_extensions_test_app(
                                          SimpleExtensionManager(res_ext))
        self.contenttype = 'application/json'
        self.novatenants_path = '/extensions/csco/tenants/tt/novatenants/'
        self.test_instance_data = {'novatenant': {'instance_id': 1,
                                   'instance_desc': {'key1': '1',
                                   'key2': '2'}}}

    def test_get_host(self):

        """ Test get host"""

        LOG.debug("test_get_host - START")
        req_body = json.dumps(self.test_instance_data)
        host_path = self.novatenants_path + "001/get_host"
        host_response = self.test_app.put(
                                 host_path, req_body,
                                 content_type=self.contenttype)
        self.assertEqual(200, host_response.status_int)
        LOG.debug("test_get_host - END")

    def test_get_hostBADRequest(self):

        """ Test get host bad request"""

        LOG.debug("test_get_hostBADRequest - START")
        host_path = self.novatenants_path + "001/get_host"
        host_response = self.test_app.put(
                                 host_path, 'BAD_REQUEST',
                                content_type=self.contenttype, status='*')
        self.assertEqual(400, host_response.status_int)
        LOG.debug("test_get_hostBADRequest - END")

    def test_instance_port(self):

        """ Test get instance port """

        LOG.debug("test_instance_port - START")
        req_body = json.dumps(self.test_instance_data)
        instance_port_path = self.novatenants_path + "001/get_instance_port"
        instance_port_response = self.test_app.put(
                                  instance_port_path, req_body,
                                  content_type=self.contenttype)
        self.assertEqual(200, instance_port_response.status_int)
        LOG.debug("test_instance_port - END")


class QosExtensionTest(unittest.TestCase):

    def setUp(self):

        """ Set up function """

        parent_resource = dict(member_name="tenant",
                               collection_name="extensions/csco/tenants")
        controller = qos.QosController(QuantumManager.get_plugin())
        res_ext = extensions.ResourceExtension('qos', controller,
                                             parent=parent_resource)

        self.test_app = setup_extensions_test_app(
                SimpleExtensionManager(res_ext))
        self.contenttype = 'application/json'
        self.qos_path = '/extensions/csco/tenants/tt/qos'
        self.qos_second_path = '/extensions/csco/tenants/tt/qos/'
        self.test_qos_data = {'qos': {'qos_name': 'cisco_test_qos',
                               'qos_desc': {'PPS': 50, 'TTL': 5}}}

    def test_create_qos(self):

        """ Test create qos """

        LOG.debug("test_create_qos - START")
        req_body = json.dumps(self.test_qos_data)
        index_response = self.test_app.post(self.qos_path,
                                       req_body,
                                       content_type=self.contenttype)
        self.assertEqual(200, index_response.status_int)

        # Clean Up - Delete the qos
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                   self.contenttype)
        qos_path_temp = self.qos_second_path +\
                resp_body['qoss']['qos']['id']
        qos_path = str(qos_path_temp)
        self.tearDownQos(qos_path)
        LOG.debug("test_create_qos - END")

    def test_create_qosBADRequest(self):

        """ Test create qos bad request """

        LOG.debug("test_create_qosBADRequest - START")
        index_response = self.test_app.post(self.qos_path,
                                            'BAD_REQUEST',
                                            content_type=self.contenttype,
                                            status='*')
        self.assertEqual(400, index_response.status_int)
        LOG.debug("test_create_qosBADRequest - END")

    def test_list_qoss(self):

        """ Test list qoss """

        LOG.debug("test_list_qoss - START")
        req_body1 = json.dumps(self.test_qos_data)
        create_resp1 = self.test_app.post(self.qos_path, req_body1,
                                          content_type=self.contenttype)
        req_body2 = json.dumps({'qos': {'qos_name': 'cisco_test_qos2',
                               'qos_desc': {'PPS': 50, 'TTL': 5}}})
        create_resp2 = self.test_app.post(self.qos_path, req_body2,
                                          content_type=self.contenttype)
        index_response = self.test_app.get(self.qos_path)
        self.assertEqual(200, index_response.status_int)

        # Clean Up - Delete the qos's
        resp_body1 = wsgi.Serializer().deserialize(create_resp1.body,
                                                   self.contenttype)
        qos_path1_temp = self.qos_second_path +\
                resp_body1['qoss']['qos']['id']
        qos_path1 = str(qos_path1_temp)
        resp_body2 = wsgi.Serializer().deserialize(create_resp2.body,
                                                   self.contenttype)
        qos_path2_temp = self.qos_second_path +\
                resp_body2['qoss']['qos']['id']
        qos_path2 = str(qos_path2_temp)
        self.tearDownQos(qos_path1)
        self.tearDownQos(qos_path2)
        LOG.debug("test_list_qoss - END")

    def test_show_qos(self):

        """ Test show qos """

        LOG.debug("test_show_qos - START")
        req_body = json.dumps(self.test_qos_data)
        index_response = self.test_app.post(self.qos_path, req_body,
                                            content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        show_path_temp = self.qos_second_path +\
                resp_body['qoss']['qos']['id']
        show_qos_path = str(show_path_temp)
        show_response = self.test_app.get(show_qos_path)
        self.assertEqual(200, show_response.status_int)

        # Clean Up - Delete the qos
        self.tearDownQos(show_qos_path)
        LOG.debug("test_show_qos - END")

    def test_show_qosDNE(self, qos_id='100'):

        """ Test show qos does not exist"""

        LOG.debug("test_show_qosDNE - START")
        show_path_temp = self.qos_second_path + qos_id
        show_qos_path = str(show_path_temp)
        show_response = self.test_app.get(show_qos_path, status='*')
        self.assertEqual(452, show_response.status_int)
        LOG.debug("test_show_qosDNE - END")

    def test_update_qos(self):

        """ Test update qos """

        LOG.debug("test_update_qos - START")
        req_body = json.dumps(self.test_qos_data)
        index_response = self.test_app.post(self.qos_path, req_body,
                                            content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        rename_req_body = json.dumps({'qos': {'qos_name': 'cisco_rename_qos',
                 'qos_desc': {'PPS': 50, 'TTL': 5}}})
        rename_path_temp = self.qos_second_path +\
                resp_body['qoss']['qos']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, rename_req_body)
        self.assertEqual(200, rename_response.status_int)
        self.tearDownQos(rename_path)
        LOG.debug("test_update_qos - END")

    def test_update_qosDNE(self, qos_id='100'):

        """ Test update qos does not exist """

        LOG.debug("test_update_qosDNE - START")
        rename_req_body = json.dumps({'qos': {'qos_name': 'cisco_rename_qos',
                 'qos_desc': {'PPS': 50, 'TTL': 5}}})
        rename_path_temp = self.qos_second_path + qos_id
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, rename_req_body,
                                            status='*')
        self.assertEqual(452, rename_response.status_int)
        LOG.debug("test_update_qosDNE - END")

    def test_update_qosBADRequest(self):

        """ Test update qos bad request """

        LOG.debug("test_update_qosBADRequest - START")
        req_body = json.dumps(self.test_qos_data)
        index_response = self.test_app.post(self.qos_path, req_body,
                                            content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        rename_path_temp = self.qos_second_path +\
                resp_body['qoss']['qos']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, 'BAD_REQUEST',
                                            status="*")
        self.assertEqual(400, rename_response.status_int)

        # Clean Up - Delete the Port Profile
        self.tearDownQos(rename_path)
        LOG.debug("test_update_qosBADRequest - END")

    def test_delete_qos(self):

        """ Test delte qos """

        LOG.debug("test_delete_qos - START")
        req_body = json.dumps({'qos': {'qos_name': 'cisco_test_qos',
                               'qos_desc': {'PPS': 50, 'TTL': 5}}})
        index_response = self.test_app.post(self.qos_path, req_body,
                                            content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(index_response.body,
                                                  self.contenttype)
        delete_path_temp = self.qos_second_path +\
                resp_body['qoss']['qos']['id']
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path)
        self.assertEqual(202, delete_response.status_int)
        LOG.debug("test_delete_qos - END")

    def test_delete_qosDNE(self, qos_id='100'):

        """ Test delte qos does not exist"""

        LOG.debug("test_delete_qosDNE - START")
        delete_path_temp = self.qos_second_path + qos_id
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path, status='*')
        self.assertEqual(452, delete_response.status_int)
        LOG.debug("test_delete_qosDNE - END")

    def tearDownQos(self, delete_profile_path):

        """ Tear Down Qos """

        self.test_app.delete(delete_profile_path)


class CredentialExtensionTest(unittest.TestCase):

    def setUp(self):

        """ Set up function """

        parent_resource = dict(member_name="tenant",
                               collection_name="extensions/csco/tenants")
        controller = credential.CredentialController(
                     QuantumManager.get_plugin())
        res_ext = extensions.ResourceExtension('credentials', controller,
                                             parent=parent_resource)
        self.test_app = setup_extensions_test_app(
                        SimpleExtensionManager(res_ext))
        self.contenttype = 'application/json'
        self.credential_path = '/extensions/csco/tenants/tt/credentials'
        self.cred_second_path = '/extensions/csco/tenants/tt/credentials/'
        self.test_credential_data = {'credential':
                                    {'credential_name': 'cred8',
                                    'user_name': 'newUser2',
                                    'password': 'newPasswd1'}}

    def test_list_credentials(self):

        """ Test list credentials """

        #Create Credential before listing
        LOG.debug("test_list_credentials - START")
        req_body1 = json.dumps(self.test_credential_data)
        create_response1 = self.test_app.post(
                           self.credential_path, req_body1,
                           content_type=self.contenttype)
        req_body2 = json.dumps({'credential':
                                {'credential_name': 'cred9',
                                'user_name': 'newUser2',
                                'password': 'newPasswd2'}})
        create_response2 = self.test_app.post(
                           self.credential_path, req_body2,
                           content_type=self.contenttype)
        index_response = self.test_app.get(
                         self.credential_path)
        self.assertEqual(200, index_response.status_int)
        #CLean Up - Deletion of the Credentials
        resp_body1 = wsgi.Serializer().deserialize(
                     create_response1.body, self.contenttype)
        delete_path1_temp = self.cred_second_path +\
                            resp_body1['credentials']['credential']['id']
        delete_path1 = str(delete_path1_temp)
        resp_body2 = wsgi.Serializer().deserialize(
                     create_response2.body, self.contenttype)
        delete_path2_temp = self.cred_second_path +\
                            resp_body2['credentials']['credential']['id']
        delete_path2 = str(delete_path2_temp)
        self.tearDownCredential(delete_path1)
        self.tearDownCredential(delete_path2)
        LOG.debug("test_list_credentials - END")

    def test_create_credential(self):

        """ Test create credential """

        LOG.debug("test_create_credential - START")
        req_body = json.dumps(self.test_credential_data)
        index_response = self.test_app.post(
                         self.credential_path, req_body,
                         content_type=self.contenttype)
        self.assertEqual(200, index_response.status_int)
        #CLean Up - Deletion of the Credentials
        resp_body = wsgi.Serializer().deserialize(
                    index_response.body, self.contenttype)
        delete_path_temp = self.cred_second_path +\
                           resp_body['credentials']['credential']['id']
        delete_path = str(delete_path_temp)
        self.tearDownCredential(delete_path)
        LOG.debug("test_create_credential - END")

    def test_create_credentialBADRequest(self):

        """ Test create credential bad request """

        LOG.debug("test_create_credentialBADRequest - START")
        index_response = self.test_app.post(
                              self.credential_path, 'BAD_REQUEST',
                              content_type=self.contenttype, status='*')
        self.assertEqual(400, index_response.status_int)
        LOG.debug("test_create_credentialBADRequest - END")

    def test_show_credential(self):

        """ Test show credential """

        LOG.debug("test_show_credential - START")
        req_body = json.dumps(self.test_credential_data)
        index_response = self.test_app.post(
                         self.credential_path, req_body,
                         content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(
                    index_response.body, self.contenttype)
        show_path_temp = self.cred_second_path +\
                         resp_body['credentials']['credential']['id']
        show_cred_path = str(show_path_temp)
        show_response = self.test_app.get(show_cred_path)
        self.assertEqual(200, show_response.status_int)
        LOG.debug("test_show_credential - END")

    def test_show_credentialDNE(self, credential_id='100'):

        """ Test show credential does not exist """

        LOG.debug("test_show_credentialDNE - START")
        show_path_temp = self.cred_second_path + credential_id
        show_cred_path = str(show_path_temp)
        show_response = self.test_app.get(show_cred_path, status='*')
        self.assertEqual(451, show_response.status_int)
        LOG.debug("test_show_credentialDNE - END")

    def test_update_credential(self):

        """ Test update credential """

        LOG.debug("test_update_credential - START")
        req_body = json.dumps(self.test_credential_data)

        index_response = self.test_app.post(
                        self.credential_path, req_body,
                        content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(
                    index_response.body, self.contenttype)
        rename_req_body = json.dumps({'credential':
                                      {'credential_name': 'cred3',
                                          'user_name': 'RenamedUser',
                                          'password': 'Renamedpassword'}})
        rename_path_temp = self.cred_second_path +\
                           resp_body['credentials']['credential']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, rename_req_body)
        self.assertEqual(200, rename_response.status_int)
        # Clean Up - Delete the Credentials
        self.tearDownCredential(rename_path)
        LOG.debug("test_update_credential - END")

    def test_update_credBADReq(self):

        """ Test update credential bad request """

        LOG.debug("test_update_credBADReq - START")
        req_body = json.dumps(self.test_credential_data)
        index_response = self.test_app.post(
                        self.credential_path, req_body,
                        content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(
                    index_response.body, self.contenttype)
        rename_path_temp = self.cred_second_path +\
                           resp_body['credentials']['credential']['id']
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, 'BAD_REQUEST',
                                            status='*')
        self.assertEqual(400, rename_response.status_int)
        LOG.debug("test_update_credBADReq - END")

    def test_update_credentialDNE(self, credential_id='100'):

        """ Test update credential does not exist"""

        LOG.debug("test_update_credentialDNE - START")
        rename_req_body = json.dumps({'credential':
                                      {'credential_name': 'cred3',
                                          'user_name': 'RenamedUser',
                                          'password': 'Renamedpassword'}})
        rename_path_temp = self.cred_second_path + credential_id
        rename_path = str(rename_path_temp)
        rename_response = self.test_app.put(rename_path, rename_req_body,
                                            status='*')
        self.assertEqual(451, rename_response.status_int)
        LOG.debug("test_update_credentialDNE - END")

    def test_delete_credential(self):

        """ Test delete credential """

        LOG.debug("test_delete_credential - START")
        req_body = json.dumps(self.test_credential_data)
        index_response = self.test_app.post(
                         self.credential_path, req_body,
                         content_type=self.contenttype)
        resp_body = wsgi.Serializer().deserialize(
                    index_response.body, self.contenttype)
        delete_path_temp = self.cred_second_path +\
                           resp_body['credentials']['credential']['id']
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path)
        self.assertEqual(202, delete_response.status_int)
        LOG.debug("test_delete_credential - END")

    def test_delete_credentialDNE(self, credential_id='100'):

        """ Test delete credential does not exist """

        LOG.debug("test_delete_credentialDNE - START")
        delete_path_temp = self.cred_second_path + credential_id
        delete_path = str(delete_path_temp)
        delete_response = self.test_app.delete(delete_path, status='*')
        self.assertEqual(451, delete_response.status_int)
        LOG.debug("test_delete_credentialDNE - END")

    def tearDownCredential(self, delete_path):
        self.test_app.delete(delete_path)


def app_factory(global_conf, **local_conf):
    conf = global_conf.copy()
    conf.update(local_conf)
    return ExtensionsTestApp(conf)


def setup_extensions_middleware(extension_manager=None):
    extension_manager = (extension_manager or
                         PluginAwareExtensionManager(EXTENSIONS_PATH,
                                                     L2Network()))
    options = {'config_file': TEST_CONF_FILE}
    conf, app = config.load_paste_app('extensions_test_app', options, None)
    return ExtensionMiddleware(app, conf, ext_mgr=extension_manager)


def setup_extensions_test_app(extension_manager=None):
    return TestApp(setup_extensions_middleware(extension_manager))


class SimpleExtensionManager(object):

    def __init__(self, resource_ext=None, action_ext=None, request_ext=None):
        self.resource_ext = resource_ext
        self.action_ext = action_ext
        self.request_ext = request_ext

    def get_resources(self):
        resource_exts = []
        if self.resource_ext:
            resource_exts.append(self.resource_ext)
        return resource_exts

    def get_actions(self):
        action_exts = []
        if self.action_ext:
            action_exts.append(self.action_ext)
        return action_exts

    def get_request_extensions(self):
        request_extensions = []
        if self.request_ext:
            request_extensions.append(self.request_ext)
        return request_extensions