CREATE RESOURCE UNIT IF NOT EXISTS alipay_unit
  MEMORY_SIZE = '2G',
  MAX_CPU = 2,
  MIN_CPU = 1,
  LOG_DISK_SIZE = '4G';

CREATE RESOURCE POOL IF NOT EXISTS alipay_pool
  UNIT = 'alipay_unit',
  UNIT_NUM = 1,
  ZONE_LIST = ('zone1', 'zone2', 'zone3');

CREATE TENANT IF NOT EXISTS alipay_tenant
  PRIMARY_ZONE = 'zone1;zone2,zone3',
  RESOURCE_POOL_LIST = ('alipay_pool')
  SET ob_compatibility_mode = 'mysql',
      ob_tcp_invited_nodes = '%';

ALTER TENANT alipay_tenant SET VARIABLES ob_tcp_invited_nodes = '%';
