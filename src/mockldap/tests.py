from __future__ import absolute_import

from doctest import DocTestSuite
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import ldap
import ldap.modlist

from . import MockLdap


manager = ("cn=Manager,ou=example,o=test", {
    "userPassword": ["ldaptest"],
    "objectClass": ["top", "posixAccount", "inetOrgPerson"]})
alice = ("cn=alice,ou=example,o=test", {
    "userPassword": ["alicepw"], "objectClass": ["top", "posixAccount"]})
bob = ("cn=bob,ou=other,o=test", {
    "userPassword": ["bobpw", "bobpw2"], "objectClass": ["top"]})
theo = ("cn=theo,ou=example,o=test", {"userPassword": [
    "{CRYPT}$1$95Aqvh4v$pXrmSqYkLg8XwbCb4b5/W/",
    "{CRYPT}$1$G2delXmX$PVmuP3qePEtOYkZcMa2BB/"],
    "objectClass": ["top", "posixAccount"]})
john = ("cn=john,ou=example,o=test", {"objectClass": ["top"]})

directory = dict([manager, alice, bob, theo, john])


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()

    suite.addTests(tests)
    suite.addTest(DocTestSuite('mockldap.recording'))

    return suite


class TestLDAPObject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mockldap = MockLdap(directory)

    def setUp(self):
        self.mockldap.start()
        self.ldapobj = self.mockldap['ldap://localhost']

    def tearDown(self):
        self.mockldap.stop()

    def test_set_option(self):
        self.ldapobj.set_option(ldap.OPT_X_TLS_DEMAND, True)
        self.assertEqual(self.ldapobj.get_option(ldap.OPT_X_TLS_DEMAND), True)

    def test_simple_bind_s_success(self):
        self.assertEqual(self.ldapobj.simple_bind_s(
            "cn=alice,ou=example,o=test", "alicepw"), (97, []))

    def test_simple_bind_s_success_case_insensitive(self):
        self.assertEqual(self.ldapobj.simple_bind_s(
            "cn=manager,ou=Example,o=test", "ldaptest"), (97, []))

    def test_simple_bind_s_anon_user(self):
        self.assertEqual(self.ldapobj.simple_bind_s(), (97, []))

    def test_simple_bind_s_raise_no_such_object(self):
        self.assertRaises(ldap.NO_SUCH_OBJECT, self.ldapobj.simple_bind_s,
                          "cn=blah,o=test", "password")

    def test_simple_bind_s_fail_login(self):
        self.assertRaises(ldap.INVALID_CREDENTIALS, self.ldapobj.simple_bind_s,
                          "cn=alice,ou=example,o=test", "wrong")

    def test_simple_bind_s_secondary_password(self):
        self.assertEqual(
            self.ldapobj.simple_bind_s("cn=bob,ou=other,o=test", "bobpw2"),
            (97, []))

    def test_simple_bind_s_success_crypt_password(self):
        self.assertEqual(
            self.ldapobj.simple_bind_s("cn=theo,ou=example,o=test", "theopw"),
            (97, []))

    def test_simple_bind_s_success_crypt_secondary_password(self):
        self.assertEqual(
            self.ldapobj.simple_bind_s("cn=theo,ou=example,o=test", "theopw2"),
            (97, []))

    def test_simple_bind_s_fail_crypt_password(self):
        self.assertRaises(ldap.INVALID_CREDENTIALS, self.ldapobj.simple_bind_s,
                          "cn=theo,ou=example,o=test", "theopw3")

    def test_search_s_get_directory_items_with_scope_onelevel(self):
        result = []
        for key, attrs in self.ldapobj.directory.items():
            if key.endswith("ou=example,o=test"):
                result.append((key, attrs))
        self.assertEqual(self.ldapobj.search_s("ou=example,o=test",
                                               ldap.SCOPE_ONELEVEL), result)

    def test_search_s_get_all_directory_items_with_scope_subtree(self):
        result = []
        for key, attrs in self.ldapobj.directory.items():
            if key.endswith("o=test"):
                result.append((key, attrs))
        self.assertEqual(self.ldapobj.search_s("o=test",
                                               ldap.SCOPE_SUBTREE), result)

    def test_search_s_get_specific_item_with_scope_base(self):
        result = [("cn=alice,ou=example,o=test",
                   self.ldapobj.directory["cn=alice,ou=example,o=test"])]
        self.assertEqual(self.ldapobj.search_s("cn=alice,ou=example,o=test",
                                               ldap.SCOPE_BASE), result)

    def test_search_s_get_specific_attr(self):
        result = [("cn=alice,ou=example,o=test",
                   {"userPassword": ["alicepw"]})]
        self.assertEqual(self.ldapobj.search_s(
            "cn=alice,ou=example,o=test", ldap.SCOPE_BASE,
            attrlist=["userPassword"]), result)

    def test_search_s_use_attrsonly(self):
        result = [("cn=alice,ou=example,o=test", {"userPassword": []})]
        self.assertEqual(self.ldapobj.search_s(
            "cn=alice,ou=example,o=test", ldap.SCOPE_BASE,
            attrlist=["userPassword"], attrsonly=1), result)

    def test_search_s_specific_attr_in_filterstr(self):
        self.assertEqual(self.ldapobj.search_s(
            "ou=example,o=test", ldap.SCOPE_ONELEVEL,
            '(userPassword=alicepw)'), [alice])

    def test_search_s_invalid_filterstr(self):
        self.assertEqual(self.ldapobj.search_s(
            "ou=example,o=test", ldap.SCOPE_ONELEVEL, '(invalid=*)'), [])

    def test_search_s_get_items_that_have_userpassword_set(self):
        self.assertEqual(self.ldapobj.search_s(
            "ou=example,o=test", ldap.SCOPE_ONELEVEL, '(userPassword=*)'),
            [alice, manager, theo])

    def test_search_s_mutliple_filterstr_items_with_and(self):
        self.assertEqual(self.ldapobj.search_s(
            "o=test", ldap.SCOPE_SUBTREE,
            "(&(objectClass=top)(objectClass=posixAccount)(userPassword=*))"),
            [alice, manager, theo])

    def test_search_s_mutliple_filterstr_items_one_invalid_with_and(self):
        self.assertEqual(self.ldapobj.search_s(
            "o=test", ldap.SCOPE_SUBTREE,
            "(&(objectClass=top)(invalid=yo)(objectClass=posixAccount))"), [])

    def test_search_s_multiple_filterstr_items_with_or(self):
        self.assertEqual(self.ldapobj.search_s(
            "o=test", ldap.SCOPE_SUBTREE,
            "(|(objectClass=inetOrgPerson)(userPassword=bobpw2))"),
            [bob, manager])

    def test_search_s_multiple_filterstr_items_one_invalid_with_or(self):
        self.assertEqual(self.ldapobj.search_s(
            "o=test", ldap.SCOPE_SUBTREE,
            "(|(objectClass=inetOrgPerson)(invalid=yo)(userPassword=bobpw2))"),
            [bob, manager])

    def test_search_s_scope_base_no_such_object(self):
        self.assertRaises(ldap.NO_SUCH_OBJECT, self.ldapobj.search_s,
                          "cn=blah,ou=example,o=test", ldap.SCOPE_BASE)

    def test_search_s_no_results(self):
        self.assertEqual(self.ldapobj.search_s(
            "ou=example,o=test", ldap.SCOPE_ONELEVEL, '(uid=blah)'), [])

    def test_start_tls_s_disabled_by_default(self):
        self.assertEqual(self.ldapobj.tls_enabled, False)

    def test_start_tls_s_enabled(self):
        self.ldapobj.start_tls_s()
        self.assertEqual(self.ldapobj.tls_enabled, True)

    def test_compare_s_no_such_object(self):
        self.assertRaises(ldap.NO_SUCH_OBJECT, self.ldapobj.compare_s,
                          'cn=blah,ou=example,o=test', 'objectClass', 'top')

    def test_compare_s_undefined_type(self):
        self.assertRaises(ldap.UNDEFINED_TYPE, self.ldapobj.compare_s,
                          'cn=alice,ou=example,o=test', 'objectClass1', 'top')

    def test_compare_s_true(self):
        self.assertEqual(self.ldapobj.compare_s(
            'cn=Manager,ou=example,o=test', 'objectClass', 'top'), 1)

    def test_compare_s_false(self):
        self.assertEqual(self.ldapobj.compare_s(
            'cn=Manager,ou=example,o=test', 'objectClass', 'invalid'), 0)

    def test_add_s(self):
        dn = 'cn=mike,ou=example,o=test'
        attrs = {
            'objectClass': ['top', 'organizationalRole'],
            'cn': ['mike'],
            'userPassword': ['mikepw'],
        }
        ldif = ldap.modlist.addModlist(attrs)
        self.assertEqual(self.ldapobj.add_s(dn, ldif), (105, [], 1, []))
        self.assertEqual(self.ldapobj.directory[dn], attrs)

    def test_add_s_already_exists(self):
        attrs = {'cn': ['mike']}
        ldif = ldap.modlist.addModlist(attrs)
        self.assertRaises(ldap.ALREADY_EXISTS, self.ldapobj.add_s, alice[0],
                          ldif)
        self.assertNotEqual(self.ldapobj.directory[alice[0]], attrs)

    def test_modify_s_replace_value_of_attribute(self):
        new_pw = ['alice', 'alicepw2']
        mod_list = [(ldap.MOD_REPLACE, 'userPassword', new_pw)]
        result = self.ldapobj.modify_s(alice[0], mod_list)
        self.assertEqual(result, (103, []))
        self.assertEqual(self.ldapobj.directory[alice[0]]['userPassword'],
                         new_pw)

    def test_modify_s_no_such_object(self):
        mod_list = [(ldap.MOD_REPLACE, 'userPassword', ['test'])]
        self.assertRaises(ldap.NO_SUCH_OBJECT, self.ldapobj.modify_s,
                          'ou=invalid,o=test', mod_list)


def initialize(*args, **kwargs):
    """ Dummy patch target for the tests below. """
    pass


class TestMockLdap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mockldap = MockLdap(directory)

    @classmethod
    def tearDownClass(cls):
        del cls.mockldap

    def tearDown(self):
        self.mockldap.stop_all()

    def test_uninitialized(self):
        self.assertRaises(KeyError, lambda: self.mockldap[''])

    def test_duplicate_patch(self):
        self.mockldap.start()

        self.assertRaises(ValueError, lambda: self.mockldap.start())

    def test_unbalanced_stop(self):
        self.assertRaises(ValueError, lambda: self.mockldap.stop())

    def test_stop_penultimate(self):
        self.mockldap.start()
        self.mockldap.start('mockldap.tests.initialize')
        self.mockldap.stop()

        self.assert_(self.mockldap[''] is not None)

    def test_stop_last(self):
        self.mockldap.start()
        self.mockldap.start('mockldap.tests.initialize')
        self.mockldap.stop()
        self.mockldap.stop('mockldap.tests.initialize')

        self.assertRaises(KeyError, lambda: self.mockldap[''])

    def test_initialize(self):
        self.mockldap.start()
        conn = ldap.initialize('ldap:///')

        self.assertEqual(conn.methods_called(), ['initialize'])

    def test_specific_content(self):
        tmp_directory = dict([alice, bob])
        self.mockldap.set_directory(tmp_directory, uri='ldap://example.com/')
        self.mockldap.start()
        conn = ldap.initialize('ldap://example.com/')

        self.assertEqual(conn.directory, tmp_directory)

    def test_no_default(self):
        mockldap = MockLdap()
        mockldap.start()

        self.assertRaises(KeyError, lambda: mockldap[''])

    def test_indepdendent_connections(self):
        self.mockldap.start()

        self.assertNotEqual(self.mockldap['foo'], self.mockldap['bar'])

    def test_volatile_modification(self):
        self.mockldap.start()
        conn1 = ldap.initialize('')
        conn1.directory['cn=alice,ou=example,o=test'][
            'userPassword'][0] = 'modified'
        self.mockldap.stop()

        self.mockldap.start()
        conn2 = ldap.initialize('')
        self.mockldap.stop()

        self.assertNotEqual(conn1.directory, conn2.directory)
