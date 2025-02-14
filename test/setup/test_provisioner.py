#!/usr/bin/env python3

# CORTX Python common library.
# Copyright (c) 2021 Seagate Technology LLC and/or its Affiliates
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.

import sys
import os
import traceback
import unittest
import yaml
from cortx.provisioner.provisioner import CortxProvisioner
from cortx.utils.conf_store import Conf

solution_cluster_url = "yaml://" + os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "cluster.yaml"))
solution_conf_url = "yaml://" + os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "config.yaml"))
cortx_conf_url = "yaml:///tmp/test.conf"
tmp_conf_url = "yaml:///tmp/tmp.conf"
delta_url = "yaml:///etc/cortx/changeset.conf"

def check_num_xx_keys(data):
    """Returns true if all the xxx list have respective num_xxx key."""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                check_num_xx_keys(v)
            elif isinstance(v, list):
                if not f"num_{k}" in data:
                    return False, f"The key num_{k} is not saved in Gconf"
                check_num_xx_keys(v)
    if isinstance(data, list):
        for v in data:
            check_num_xx_keys(v)
    return True, "The keys num_xx are saved in gconf"

class TestProvisioner(unittest.TestCase):
    """Test cortx_setup config and cluster functionality."""

    def test_config_apply_bootstrap(self):
        """Test Config Apply."""
        rc = 0
        try:
            CortxProvisioner.config_apply(solution_cluster_url, cortx_conf_url)
            CortxProvisioner.config_apply(solution_conf_url, cortx_conf_url, force_override=True)
        except Exception as e:
            print('Exception: ', e)
            sys.stderr.write("%s\n" % traceback.format_exc())
            rc = 1
        self.assertEqual(rc, 0)
        rc = 0
        try:
            CortxProvisioner.cluster_bootstrap(cortx_conf_url)
            CortxProvisioner.cluster_upgrade(cortx_conf_url)
        except Exception as e:
            print('Exception: ', e)
            sys.stderr.write("%s\n" % traceback.format_exc())
            rc = 1
        self.assertEqual(rc, 0)

    def test_num_xxx_in_gconf(self):
        """Test if num_xxx key is saved in gconf for list items(CORTX-30863)."""
        rc = 0
        try:
            CortxProvisioner.config_apply(solution_cluster_url, cortx_conf_url)
            CortxProvisioner.config_apply(solution_conf_url, cortx_conf_url, force_override=True)
        except Exception as e:
            print('Exception: ', e)
            sys.stderr.write("%s\n" % traceback.format_exc())
            rc = 1
        self.assertEqual(rc, 0)
        conf_path = cortx_conf_url.split('//')[1]
        rc = 0
        with open(conf_path, 'r') as stream:
            try:
                gconf = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                rc = 1
        self.assertEqual(rc, 0)
        is_key_present, message = check_num_xx_keys(gconf)
        self.assertTrue(is_key_present, message)

    def test_prepare_diff(self):
        """Test if changeset file is getting generated with new/changes/deleted keys"""
        Conf.load('index1', tmp_conf_url)
        Conf.load('index2', cortx_conf_url)
        # add 1 new key in tmp conf
        Conf.set('index1', 'cortx>common>name', 'CORTX')
        # Change previous key from tmp conf
        Conf.set('index1', 'cortx>common>security>device_certificate', '/etc/cortx/solution/security.pem')
        # Delete one key from tmp conf
        Conf.delete('index1', 'cortx>common>security>domain_certificate')
        Conf.save('index1')
        rc = 0
        try:
            CortxProvisioner._prepare_diff('index2','index1', 'index3')
        except Exception as e:
            print('Exception: ', e)
            sys.stderr.write("%s\n" % traceback.format_exc())
            rc = 1
        self.assertEqual(rc, 0)
        self.assertEqual(Conf.get('index3','new>cortx>common>name'),'CORTX')

    def test_update_conf(self):
        """Test if new keys from changeset are getting updated in conf"""
        rc = 0
        try:
            CortxProvisioner._update_conf('index2','index1')
        except Exception as e:
            print('Exception: ', e)
            sys.stderr.write("%s\n" % traceback.format_exc())
            rc = 1
        self.assertEqual(rc, 0)
        self.assertEqual(Conf.get('index2','cortx>common>name'),'CORTX')

if __name__ == '__main__':
    unittest.main()
