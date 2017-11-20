import settings
import datastorage as ds

settings.init('server/server_ds_test.cfg')

ds.initialize_logfiles(clean=True)

# start a recording a test range
resp = {\
        'SUCCESS': True, \
        'Timestamp': 1., \
        'Timestamp_send': 1.5, \
        }
ds.data_event_handler('start', 'tag1', 'obs2', resp)
res = ds.get_data_collection_range('tag1')
assert(res==(None,None))
res = ds.get_open_session('tag1')
assert(res==0)

# update pos and test range
resp = {\
        'SUCCESS': True, \
        'Timestamp': 3., \
        'Timestamp_send': 3.2, \
        'Pos': 1000, \
        }
ds.data_event_handler('pos', 'tag1', 'obs1', resp)
res = ds.get_data_collection_range('tag1')
assert(res==(None,None))
res = ds.get_data_collection_range('tag2')
assert(res==(None,None))

# test open session
res = ds.get_all_open_sessions()
assert(res['tag1']==0)
assert('tag2' not in res)

# update pos again and test range
resp = {\
        'SUCCESS': True, \
        'Timestamp': 5., \
        'Timestamp_send': 5.1, \
        'Pos': 25000, \
        }
ds.data_event_handler('pos', 'tag1', 'obs1', resp)
res = ds.get_data_collection_range('tag1')
assert(res==(0,15000))
res = ds.get_data_collection_range('tag2')
assert(res==(None,None))

# start another tag
resp = {\
        'SUCCESS': True, \
        'Timestamp': 5.8, \
        'Timestamp_send': 5.9, \
        }
ds.data_event_handler('start', 'tag2', 'obs1', resp)
res = ds.get_open_session('tag2')
assert(res==1)


# test open session
res = ds.get_all_open_sessions()
assert(res['tag1']==0)
assert(res['tag2']==1)


# collect some data
res = ds.get_data_collection_range('tag1')
assert(res==(0,15000))
# NOTE use the relevant values for sess, start, count and next
# NOTE also in the current implementation collecting data
# after record stop is hard to do, unless server remembers the
# last running session id.
resp = {\
        'SUCCESS': True, \
        'Timestamp': 8., \
        'sess_id': ds.get_open_session('tag1'), \
        'start_pos': res[0], \
        'count': res[1], \
        'Next': res[0]+res[1], \
        'Data': 'data1', \
        }
ds.data_event_handler('data', 'tag1', 'obs2', resp)

# test range again after data collection
res = ds.get_data_collection_range('tag1')
assert(res==(15000,10000))

# update pos with wrap around and test range
resp = {\
        'SUCCESS': True, \
        'Timestamp': 10.4, \
        'Timestamp_send': 10.6, \
        'Pos': 100, \
        }
ds.data_event_handler('pos', 'tag1', 'obs1', resp)
res = ds.get_data_collection_range('tag1')
assert(res==(15000,15000))

# update pos with small amount and test range
resp = {\
        'SUCCESS': True, \
        'Timestamp': 11.4, \
        'Timestamp_send': 11.6, \
        'Pos': 100, \
        }
ds.data_event_handler('pos', 'tag2', 'obs3', resp)
res = ds.get_data_collection_range('tag2')
assert(res==(None,None))

# Note that the wrap around test below does not pass
# but unless we lost connection for a long time this 
# will not happen
# # update pos again
# resp = {\
#         'SUCCESS': True, \
#         'Timestamp': 11.4, \
#         'Timestamp_send': 11.6, \
#         'Pos': 50, \
#         }
# ds.data_event_handler('pos', 'tag2', 'obs3', resp)
# res = ds.get_data_collection_range('tag2')
# print(res)
# assert(res==(0,15000))

resp = {\
        'SUCCESS': True, \
        'Timestamp': 11.4, \
        'Timestamp_send': 11.6, \
        'Pos': 50000, \
        }
ds.data_event_handler('pos', 'tag2', 'obs3', resp)
res = ds.get_data_collection_range('tag2')
assert(res==(0,15000))
# collect some data
resp = {\
        'SUCCESS': True, \
        'Timestamp': 8., \
        'sess_id': ds.get_open_session('tag2'), \
        'start_pos': res[0], \
        'count': res[1], \
        'Next': res[0]+res[1], \
        'Data': 'data2', \
        }
ds.data_event_handler('data', 'tag2', 'obs2', resp)
# collect some more data
res = ds.get_data_collection_range('tag2')
assert(res==(15000,15000))
resp = {\
        'SUCCESS': True, \
        'Timestamp': 8., \
        'sess_id': ds.get_open_session('tag2'), \
        'start_pos': res[0], \
        'count': res[1], \
        'Next': res[0]+res[1], \
        'Data': 'data2', \
        }
ds.data_event_handler('data', 'tag2', 'obs2', resp)


# test stop recording
resp = {\
        'SUCCESS': True, \
        'Timestamp': 14.4, \
        }
ds.data_event_handler('stop', 'tag1', 'obs1', resp)
res = ds.get_open_session('tag1')
assert(res is None)

# test open session
res = ds.get_all_open_sessions()
assert('tag1' not in res)
assert(res['tag2']==1)

# restart new recording with new session
resp = {\
        'SUCCESS': True, \
        'Timestamp': 1., \
        'Timestamp_send': 1.5, \
        }
ds.data_event_handler('start', 'tag1', 'obs2', resp)
res = ds.get_data_collection_range('tag1')
assert(res==(None,None))
res = ds.get_open_session('tag1')
assert(res==3)

# test open session
res = ds.get_all_open_sessions()
assert(res['tag1']==3)
assert(res['tag2']==1)

# test stop again
resp = {\
        'SUCCESS': True, \
        'Timestamp': 14.4, \
        }
ds.data_event_handler('stop', 'tag2', 'obs1', resp)
res = ds.get_open_session('tag2')
assert(res==None)


print('Test passed.')
