import pandas as pd
import numpy as np
import keras

from keras.models import Model
from keras.layers import Input, Dense
from keras.layers.merge import Multiply, Dot, Concatenate
from keras.initializers import Zeros as ZeroInit
from keras.initializers import Ones as OneInit
from keras.optimizers import Adam

fname = 'g_calib.txt'
valid_frac = 0.9
df = pd.read_csv(fname)
x_train = np.array(df)
y_train = np.ones(x_train.shape[0])
valid_size = int(x_train.shape[0]*valid_frac)

x = Input(shape=(1,), name='input_x')
y = Input(shape=(1,), name='input_y')
z = Input(shape=(1,), name='input_z')
calib_x = Dense(1, name='calib_x', \
        kernel_initializer = OneInit(), \
        bias_initializer = ZeroInit())(x)
calib_y = Dense(1, name='calib_y', \
        kernel_initializer = OneInit(), \
        bias_initializer = ZeroInit())(y)
calib_z = Dense(1, name='calib_z', \
        kernel_initializer = OneInit(), \
        bias_initializer = ZeroInit())(z)
calib_layer = Concatenate()([calib_x,calib_y,calib_z])
total_acc = Dot(1)([calib_layer, calib_layer])
model = Model(inputs=[x,y,z], outputs=total_acc)

for lr in [0.05, 0.01]:
    model.compile(optimizer=Adam(lr), loss='mse')
    model.summary()
    model.fit([x_train[:,0], x_train[:,1], x_train[:,2]], y_train, epochs=20, batch_size=valid_size,\
            validation_split = (1-valid_frac))

print(model.get_weights())

