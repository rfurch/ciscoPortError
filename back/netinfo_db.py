import   time
import   re
import   logging
import   pyodbc   # For python3 MSSQL

import   settings   

#_DB_SERVER = 'BRJTXSNSRV01.bar.nucorsteel.local'
_DB_SERVER = '10.14.2.227'
_DB_DATABASE = 'networkInfo'
_DB_USER = 'JewettTests'
_DB_PASS = '#NstxErcot#'

_sql_conn=None

## ------------------------------------------------------------------
## ------------------------------------------------------------------

## DB Connect
    
async def dbConnect():

  try:
    conn_string = 'DRIVER={ODBC Driver 18 for SQL Server};' 'SERVER=' + _DB_SERVER + ';DATABASE=' + _DB_DATABASE + \
                    ';UID=' + _DB_USER + ';PWD=' + _DB_PASS + ';Encrypt=No'

    print (conn_string)  
    _sql_conn = pyodbc.connect(conn_string)
  except Exception as e:  
    print ("Exception:::", e)
    logging.info("Exception:::")
    logging.info(e)
  return(_sql_conn)

## ------------------------------------------------------------------

## DB Close
   
async def dbClose(conn):
  conn.close()
  return(None)

## ------------------------------------------------------------------
  
## get ID  BRJTXSNSRV01  networkInfo   DEVICES  for a given hostname
    
async def dbGetDeviceID(dbConn, hostname):

  devID = None
  adminIP = None

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    #return None
    return (0,0)  
  if (hostname is None):
    logging.info('Hostname invalid. !!')
    #return None
    return (0,0)

  try:
    dbCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  dbStr = '''SELECT id, adminIP FROM [networkInfo].[dbo].[devices] where hostname like '{}' '''.format( hostname )
  #print(dbStr)

  try:
    dbCursor.execute(dbStr)
      
    for row in dbCursor.fetchall():  ## if several hostnames, get last.... 
      #print (row[0])
      devID = row[0]
      
      if (row[1] is not None):
        adminIP = row[1].strip()
      
  except Exception as e:  
    print("DB Operation failed...({})".format(dbStr))
    logging.info('DB ERROR : Merge error!!')
  	      
  dbConn.commit() 
  dbCursor.close()
  return( (devID, adminIP) )


## ------------------------------------------------------------------
  
  
## get IPs for devices not updated in X minutes
    
async def dbGetDeviceNotUpdated(dbConn, minutesBack):

  devicesNotUpdated = []
  devID = None
  adminIP = None

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (minutesBack is None):
    logging.info('minutesBack invalid. !!')
    return None

  try:
    dbCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  dbStr = '''   SELECT IIF( LEN(TRIM([adminIP])) > 6, [adminIP], [ip] ) AS IP 
  FROM [networkInfo].[dbo].[devices]  where DATEDIFF(minute, lastUpdate, getdate()) > {} '''.format( minutesBack )
  #print(dbStr)

  try:
    dbCursor.execute(dbStr)
      
    for row in dbCursor.fetchall():  ## if several hostnames, get last.... 
      if (row[0] is not None):
        devicesNotUpdated.append(row[0].strip())
      
  except Exception as e:  
    print("DB Operation failed...({})".format(dbStr))
    logging.info('DB ERROR : Merge error!!')
  	      
  dbConn.commit() 
  dbCursor.close()
  return( (devicesNotUpdated) )


## ------------------------------------------------------------------
  
  
async def updateNeighbors(dbConn, ip,  devHostname, neighborsList):

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (devHostname is None):
    logging.info('devHostname invalid. !!')
    return None
  if (neighborsList is None):
    logging.info('neighborsList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('updateNeighbors ERROR : {}'.format(e))
    return (None) 

  for d in neighborsList:
    insertStr = '''MERGE [networkInfo].[dbo].[neighbors] WITH (SERIALIZABLE) AS T
      USING (VALUES ('{}', '{}', '{}', '{}', GETDATE())) AS 
      U ([hostname] , [ip] , [neighborHostname]  , [neighborIP]  , [lastUpdate])
      ON U.[hostname] = T.[hostname] AND U.[neighborHostname] = T.[neighborHostname]
      WHEN MATCHED THEN
      UPDATE 
      SET T.[ip] = U.[ip], T.[neighborIP] = U.[neighborIP], 
      T.[lastUpdate] = U.[lastUpdate]
      WHEN NOT MATCHED THEN
      INSERT ([hostname], [ip], [neighborHostname], [neighborIP], [lastUpdate])
      VALUES (U.[hostname], U.[ip], U.[neighborHostname], U.[neighborIP], U.[lastUpdate]);
      '''.format(devHostname, ip, d['name'], d['ip'] )
        
    if (settings.verbose):
      print(insertStr)

    try:
      insertCursor.execute(insertStr)
    except Exception as e:  
      print("DB OPERATION failed...({})".format(insertStr))
      logging.info('DB ERROR : Merge error!!')

  dbConn.commit() 
  insertCursor.close()
  return()

## ------------------------------------------------------------------
  
## update into BRJTXSNSRV01  networkInfo   DEVICES, as NON SSH ACCESSIBLE
    
async def dbUpdateUnaccesibleDevices(dbConn, ip):

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if ( ip is None or len(ip) < 5 ):
    logging.info('IP address invalid. !!')
    return None

  try:
    sqlCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  sqlStr = '''UPDATE [networkInfo].[dbo].[devices] SET [sshAccessOK] = 0 WHERE [ip] like '{}';'''.format( ip )
        
  try:
    sqlCursor.execute(sqlStr)
  except Exception as e:  
    print("DB OPERATION failed... (ip: {}  sqlStr: {} )".format(ip, sqlStr))
    logging.info('DB ERROR : Merge error!!  (ip: {}  sqlStr: {}'.format(ip, sqlStr))
  	
  dbConn.commit() 
  sqlCursor.close()
  return()

## ------------------------------------------------------------------
  
## insert/update into BRJTXSNSRV01  networkInfo   DEVICES
    
async def dbUpdateDevices(dbConn, deviceList):

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (deviceList is None):
    logging.info('deviceList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  #print(deviceList)
  for d in deviceList:
    insertStr = '''MERGE [networkInfo].[dbo].[devices] WITH (SERIALIZABLE) AS T
      USING (VALUES ('{}', '{}', '{}', '{}', '{}', 1, GETDATE())) AS U ([hostname], [serialNum], [ip], [uptime], [platform], [sshAccessOK], [lastUpdate])
      ON U.[hostname] = T.[hostname]
      WHEN MATCHED THEN 
        UPDATE SET T.[serialNum] = U.[serialNum], T.[ip] = U.[ip], T.[lastUpdate] = U.[lastUpdate], 
        T.[uptime] = U.[uptime] , T.[sshAccessOK] = U.[sshAccessOK], T.[platform] = U.[platform] 
      WHEN NOT MATCHED THEN
        INSERT ([hostname], [serialNum], [ip], [uptime], [platform], [sshAccessOK], [lastUpdate]) 
        VALUES (U.[hostname], U.[serialNum], U.[ip], U.[uptime], U.[platform], U.[sshAccessOK], U.[lastUpdate]);
      '''.format(d['hostname'], d['serialNum'], d['ip'], d['uptime'] , d['platform'] )
        
    if (settings.verbose):
      print(insertStr)

    try:
      insertCursor.execute(insertStr)
    except Exception as e:  
      print("DB OPERATION failed...({})".format(insertStr))
      logging.info('DB ERROR : Merge error!!')
  	
  dbConn.commit() 
  insertCursor.close()
  return()


## ------------------------------------------------------------------
  
## insert/update into BRJTXSNSRV01  networkInfo    ARP 
    
async def dbUpdateARPList(dbConn, arpList, hostname):

  counter = 0

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (arpList is None):
    logging.info('arpList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  #print(arpList)
  for d in arpList:
    sqlStr = '''MERGE [networkInfo].[dbo].[arp] WITH (SERIALIZABLE) AS T
      USING (VALUES ({}, '{}', '{}', '{}', '{}', GETDATE())) AS U ([deviceID] ,[mac]  ,[ip]  ,[vlan]  ,[age]  ,[lastUpdate])
      ON U.[deviceID] = T.[deviceID] AND U.[mac] = T.[mac] AND U.[ip] = T.[ip] 
      WHEN MATCHED THEN
        UPDATE SET T.[deviceID] = U.[deviceID], T.[ip] = U.[ip], T.[lastUpdate] = U.[lastUpdate], T.[mac] = U.[mac], T.[age] = U.[age]
      WHEN NOT MATCHED THEN
        INSERT ([deviceID] ,[mac]  ,[ip]  ,[vlan]  ,[age]  ,[lastUpdate])
        VALUES (U.[deviceID], U.[mac], U.[ip], U.[vlan], U.[age], U.[lastUpdate]);
      '''.format(d['id'], d['mac'], d['ip'], d['vlanNum'] , d['age'] )
    #print(sqlStr)

    try:
      insertCursor.execute(sqlStr)
      counter += 1
      if ( (counter % 100) == 0 ):
        time.sleep(0.15)   

    except Exception as e:  
      print("DB Operation failed...(hostname: {} SQLString: {})".format(hostname,sqlStr))
      logging.info('DB ERROR : Merge error!! (hostname: {} SQLString: {}'.format(hostname,sqlStr))
  	
  dbConn.commit() 
  insertCursor.close()
  return()


## ------------------------------------------------------------------
  
## insert/update into BRJTXSNSRV01  networkInfo    MAC 
    
async def dbUpdateMACList(dbConn, macList, hostname):

  counter = 0

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (macList is None):
    logging.info('macList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  #print(macList)
  for d in macList:
    sqlStr = '''MERGE [networkInfo].[dbo].[mac] WITH (SERIALIZABLE) AS T
      USING (VALUES ({}, {}, '{}', '{}', '{}', GETDATE())) AS U ([deviceID] , [vlan], [mac] ,[type]  ,[port]  ,[lastUpdate])
      ON U.[deviceID] = T.[deviceID] AND U.[mac] = T.[mac] AND U.[vlan] = T.[vlan] AND U.[port] = T.[port]
      WHEN MATCHED THEN
        UPDATE SET T.[deviceID] = U.[deviceID], T.[vlan] = U.[vlan], T.[lastUpdate] = U.[lastUpdate], T.[mac] = U.[mac], T.[port] = U.[port], T.[type] = U.[type]
      WHEN NOT MATCHED THEN
        INSERT ([deviceID] ,[mac]  ,[port]  ,[vlan]  ,[type]  ,[lastUpdate])
        VALUES (U.[deviceID], U.[mac], U.[port], U.[vlan], U.[type], U.[lastUpdate]);
      '''.format(d['id'], d['vlanNum'], d['mac'], d['type'], d['port'] )
    #print(sqlStr)

    try:
      insertCursor.execute(sqlStr)
      counter += 1
      if ( (counter % 100) == 0 ):
        time.sleep(0.15)   

    except Exception as e:  
      print("DB Operation failed...(hostname: {})".format(hostname))
      logging.info('DB ERROR : Merge error!! (hostname: {}'.format(hostname))
  	
  dbConn.commit() 
  insertCursor.close()
  return()


## ------------------------------------------------------------------
  
## insert/update into BRJTXSNSRV01  networkInfo    interfaces 
## {'id': 88, 'port': 'Gi1/0/1', 'descr': 'SPARE', 'status': 'notconnect', 'vlan': '999', 'vlanNum': 999, 'duplex': 'auto', 'speed': 'auto', 'type': '10/100/1000BaseTX'}
    
async def dbUpdateiFaceList(dbConn, iFaceList, hostname):

  counter = 0

  if (dbConn is None):
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (iFaceList is None):
    logging.info('iFaceList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateDevices ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  #print(iFaceList)
  for d in iFaceList:
    if d is not None:
      sqlStr = '''MERGE [networkInfo].[dbo].[interfaces] WITH (SERIALIZABLE) AS T
        USING (VALUES ({}, '{}', '{}', '{}', '{}', {}, '{}', '{}', '{}', GETDATE())) AS U 
        ([deviceID] , [name], [description] , [status]  ,[vlan]  ,[vlanNumber], [type] ,[speed], [duplex],[lastUpdate])
        ON U.[deviceID] = T.[deviceID] AND U.[name] = T.[name]
        WHEN MATCHED THEN
          UPDATE SET T.[deviceID] = U.[deviceID], T.[name] = U.[name], T.[lastUpdate] = U.[lastUpdate], T.[description] = U.[description], 
          T.[status] = U.[status], T.[vlan] = U.[vlan], T.[vlanNumber] = U.[vlanNumber], T.[type] = U.[type], T.[speed] = U.[speed], T.[duplex] = U.[duplex]
        WHEN NOT MATCHED THEN
          INSERT ([deviceID] ,[name]  ,[description]  ,[status]  ,[vlan] ,[vlanNumber] ,[type] ,[speed] ,[duplex] ,[lastUpdate])
          VALUES (U.[deviceID], U.[name], U.[description], U.[status], U.[vlan], U.[vlanNumber], U.[type], U.[speed], U.[duplex], U.[lastUpdate]);
        '''.format(d['id'], d['port'], d['descr'], d['status'], d['vlan'], d['vlanNum'], d['type'], d['speed'], d['duplex'] )
      #print(sqlStr)

      try:
        insertCursor.execute(sqlStr)
        counter += 1
        if ( (counter % 100) == 0 ):
          time.sleep(0.15)   

      except Exception as e:  
        print("DB Operation failed...(hostname: {})".format(hostname))
        logging.info('DB ERROR : Merge error!! (hostname: {}'.format(hostname))
  	
  dbConn.commit() 
  insertCursor.close()
  return()

## ------------------------------------------------------------------
## insert/update into BRJTXSNSRV01  networkInfo    interfaces 
## {'id': 0, 'interfaceName': 'Ethernet7/3', 'inputRate': '0', 'outputRate': '0', 'inputErrors': '0', 'outputErrors': '0', 'crcErrors': '0', 'collisionErrors': '0'},

async def dbUpdateiFaceErrorList(dbConn, iFaceErrorList, hostname):

  counter = 0

  if (dbConn is None):
    logging.info('dbUpdateiFaceErrorList ERROR : DB handler invalid. Unable to access DB!!')
    return None
  if (iFaceErrorList is None):
    logging.info('dbUpdateiFaceErrorList invalid. !!')
    return None

  try:
    insertCursor = dbConn.cursor()

  except Exception as e:  
    print ("Exception:::", e)
    logging.info('dbUpdateiFaceErrorList ERROR : DB handler invalid. Unable to access DB!!')
    logging.info("Exception:::")
    logging.info(e)
    return (None) 

  #print(iFaceList)
  for d in iFaceErrorList:
    if d is not None:
      
      sqlStr = '''INSERT INTO [networkInfo].[dbo].[interfaceErrors]
        ([deviceID], [interfaceName], [inputRate], [outputRate],
        [inputErrors], [outputErrors], [crcErrors], [collisionErrors],
        [datetime])
         VALUES({}, '{}', {}, {}, {}, {}, {}, {}, GETDATE() )
         '''.format(d['id'], d['interfaceName'], d['inputRate'], 
                    d['outputRate'], d['inputErrors'], d['outputErrors'], 
                    d['crcErrors'] , d['collisionErrors'])

      if settings.debug > 2:  
        print(sqlStr)

      try:
        insertCursor.execute(sqlStr)
        counter += 1
        if ( (counter % 100) == 0 ):
          time.sleep(0.15)   

      except Exception as e:  
        print("DB Operation failed...err: {}  (hostname: {})".format(e, hostname))
        logging.info('DB ERROR : Merge error!! (hostname: {}'.format(hostname))
  	
  dbConn.commit() 
  insertCursor.close()
  return()


## ------------------------------------------------------------------
## ------------------------------------------------------------------
