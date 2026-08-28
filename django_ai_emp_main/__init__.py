import pymysql
from django.db.backends.base.base import BaseDatabaseWrapper

# 1. Tell Django to use PyMySQL
pymysql.install_as_MySQLdb()

# 2. Force Django to skip the MySQL version check
BaseDatabaseWrapper.check_database_version_supported = lambda _: None