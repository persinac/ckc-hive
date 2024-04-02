import subprocess
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_DRIVER = "org.postgresql.Driver"
DATABASE_TYPE_JDBC = "postgresql"
DATABASE_PORT = "25060"
DATABASE_TYPE = "postgres"
DATABASE_VALIDATION_SUCCESS_KEYWORD = "Done with metastore validation [SUCCESS]"

def generate_database_config():
    logging.info("generate_database_config")
    logging.info("----------------------------------")
    custom_endpoint_configs = generate_s3_custom_endpoint()
    return f"""
<property>
  <name>javax.jdo.option.ConnectionDriverName</name>
  <value>{DATABASE_DRIVER}</value>
</property>
<property>
  <name>javax.jdo.option.ConnectionURL</name>
  <value>jdbc:{DATABASE_TYPE_JDBC}://{os.getenv("PG_DB_HOST")}:{os.getenv("PG_DB_PORT")}/{os.getenv("HIVE_DATABASE_NAME")}</value>
</property>
<property>
  <name>javax.jdo.option.ConnectionUserName</name>
  <value>{os.getenv("PG_METASTORE_USER")}</value>
</property>
<property>
  <name>javax.jdo.option.ConnectionPassword</name>
  <value>{os.getenv("PG_METASTORE_USER_PW")}</value>
</property>
"""

def generate_hive_site_config(filepath):
    with open(filepath, "w") as file:
        file.write(f"<configuration>{generate_database_config()}</configuration>")

def generate_metastore_site_config(filepath):
    database_config = generate_database_config()
    with open(filepath, "w") as file:
        file.write(f"""
<configuration>
  <property>
    <name>metastore.task.threads.always</name>
    <value>org.apache.hadoop.hive.metastore.events.EventCleanerTask</value>
  </property>
  <property>
    <name>metastore.expression.proxy</name>
    <value>org.apache.hadoop.hive.metastore.DefaultPartitionExpressionProxy</value>
  </property>
  {database_config}
  <property>
    <name>metastore.warehouse.dir</name>
    <value>{os.getenv("HIVE_S3A_FULL_PATH")}</value>
  </property>
  <property>
    <name>metastore.thrift.port</name>
    <value>9083</value>
  </property>
</configuration>
""")

def generate_s3_custom_endpoint():
    return f"""
<property>
  <name>fs.s3a.endpoint</name>
  <value>s3.amazonaws.com</value>
</property>
<property>
  <name>fs.s3a.access.key</name>
  <value>{os.getenv("HIVE_S3_IAM_ACCESS_KEY")}</value>
</property>
<property>
  <name>fs.s3a.secret.key</name>
  <value>{os.getenv("HIVE_S3_IAM_SECRET_KEY")}</value>
</property>
<property>
  <name>fs.s3a.connection.ssl.enabled</name>
  <value>false</value>
</property>
<property>
  <name>fs.s3a.path.style.access</name>
  <value>true</value>
</property>
"""

def generate_core_site_config(filepath):
    logging.info("generate_core_site_config")
    logging.info(os.getenv("HIVE_S3A_BASE_VALUE"))
    logging.info("----------------------------------")
    custom_endpoint_configs = generate_s3_custom_endpoint()
    with open(filepath, "w") as file:
        file.write(f"""
<configuration>
  <property>
      <name>fs.defaultFS</name>
      <value>{os.getenv("HIVE_S3A_BASE_VALUE")}</value>
  </property>
  <property>
      <name>fs.s3a.impl</name>
      <value>org.apache.hadoop.fs.s3a.S3AFileSystem</value>
  </property>
  <property>
      <name>fs.s3a.fast.upload</name>
      <value>true</value>
  </property>
  {custom_endpoint_configs}
</configuration>
""")

def run_migrations():
    result = subprocess.run(["/opt/hive-metastore/bin/schematool", "-dbType", DATABASE_TYPE, "-validate"], capture_output=True, text=True)
    if DATABASE_VALIDATION_SUCCESS_KEYWORD in result.stdout:
        print('Database OK')
        return
    else:
        subprocess.run(["/opt/hive-metastore/bin/schematool", "--verbose", "-dbType", DATABASE_TYPE, "-initSchema"])

if __name__ == "__main__":
    generate_hive_site_config("/opt/hadoop/etc/hadoop/hive-site.xml")
    run_migrations()

    # configure & start metastore (in foreground)
    generate_metastore_site_config("/opt/hive-metastore/conf/metastore-site.xml")
    generate_core_site_config("/opt/hadoop/etc/hadoop/core-site.xml")
    subprocess.run(["/opt/hive-metastore/bin/start-metastore"])
