"""
MyAnfis Implementation
Gregor Lenhard
University of Basel
"""
import logging
logging.getLogger('tensorflow').disabled = True
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # remove WARNING Messages
import tensorflow as tf
from tensorflow import keras
import numpy as np
import matplotlib.pyplot as plt
## parameter class fis parameters
class fis_parameters():
    def __init__(self,n_input=3, n_control=None, n_memb=3, batch_size=16, n_epochs=25, memb_func='gaussian',optimizer='sgd', loss='mse'):
        self.n_input = n_input  # no. of Regressors
        self.n_control = n_control  # no. of control variables
        self.n_memb = n_memb  # no. of fuzzy memberships
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.memb_func = memb_func  # 'gaussian' / 'gbellmf'
        self.optimizer = optimizer   # sgd / adam /
        self.loss = loss     ## mse / mae


# Main Class ANFIS
class CONANFIS:
    def __init__(self, n_input, n_control, n_memb, batch_size=16, memb_func = 'gaussian', name = 'MyAnfis'):
        self.n = n_input
        self.n_control = n_control
        self.m = n_memb
        self.batch_size = batch_size
        self.memb_func = memb_func
        input_ = keras.layers.Input(shape=(n_input+n_control), name='inputLayer', batch_size = batch_size)
        #control_input_ = keras.layers.Input(shape=(n_control), name='controlInputLayer', batch_size = batch_size)
        L1 = FuzzyLayer(n_input, n_control, n_memb, memb_func, name='fuzzyLayer')(input_)
        L2 = RuleLayer(n_input, n_control, n_memb, name='ruleLayer')(L1)
        L3 = NormLayer(name='normLayer')(L2)
        L4 = DefuzzLayer(n_input, n_control, n_memb, name='defuzzLayer')(L3, input_[:,:n_input]) # without control variable
        L5 = SummationLayer(name='sumLayer')(L4)
        self.model = keras.Model(inputs=input_, outputs=[L5], name = name)
        self.update_weights()

    def __call__(self, X):       # TODO: update for control variable
        return self.model.predict(X)

    def update_weights(self):
        # premise parameters (mu&sigma for gaussian // a/b/c for bell-shaped)
        if self.memb_func == 'gaussian':
            self.mus , self.sigmas = self.model.get_layer('fuzzyLayer').get_weights()
        elif self.memb_func == 'gbellmf':
            self.a , self.b, self.c = self.model.get_layer('fuzzyLayer').get_weights()
        # consequence parameters
        self.bias, self.weights = self.model.get_layer('defuzzLayer').get_weights()

    def plotmfs(self, show_initial_weights=False):
        n_input = self.n + self.n_control
        n_memb = self.m

        if self.memb_func == 'gaussian':
            mus, sigmas = np.around(self.model.get_layer('fuzzyLayer').get_weights(),2)
            mus, sigmas = mus.reshape((n_memb, n_input, 1)), sigmas.reshape(n_memb , n_input, 1)

            xn = np.linspace(np.min(mus)-2*np.max(abs(sigmas)),np.max(mus)+2*np.max(abs(sigmas)), 100).reshape((1,1,-1))
            xn = np.tile(xn, (n_memb, n_input, 1))

            # broadcast all curves in one array
            memb_curves = np.exp(-np.square((xn-mus))/np.square(sigmas))

            if show_initial_weights:
                mus_init, sigmas_init = np.around(self.init_weights,2)
                mus_init, sigmas_init = mus_init.reshape(n_memb, n_input, 1), sigmas_init.reshape(n_memb, n_input, 1)
                init_curves = np.exp(-np.square((xn-mus_init))/np.square(sigmas_init))

        elif self.memb_func == 'gbellmf':
            a, b, c = np.around(self.model.get_layer('fuzzyLayer').get_weights(),2)
            a, b, c = a.reshape((n_memb, n_input, 1)), b.reshape(n_memb, n_input, 1), c.reshape(n_memb, n_input, 1)

            xn = np.linspace(np.min(c)-2*np.max(abs(a)),np.max(c)+2*np.max(abs(a)), 100).reshape((1,1,-1))
            xn = np.tile(xn, (n_memb, n_input, 1))

            # broadcast all curves in one array
            memb_curves= 1/(1+np.square((xn-c)/a)**b)

            if show_initial_weights:
                a_init, b_init, c_init = np.around(self.init_weights,2)
                a_init, b_init, c_init = a_init.reshape((n_memb, n_input, 1)), b_init.reshape(n_memb, n_input, 1), c_init.reshape(n_memb, n_input, 1)
                init_curves = 1/(1+np.square((xn-c_init)/a_init)**b_init)

        elif self.memb_func == 'sigmoid':
            gammas, c = np.around(self.model.get_layer('fuzzyLayer').get_weights(),2)
            gammas, c = gammas.reshape((n_memb, n_input, 1)), c.reshape(n_memb , n_input, 1)

            xn = np.linspace(np.min(c)-2*np.max(abs(c)),np.max(c)+2*np.max(abs(c)), 100).reshape((1,1,-1))  #TODO: change confidence bands
            xn = np.tile(xn, (n_memb, n_input, 1))

            # broadcast all curves in one array
            memb_curves = 1 / (1 + np.exp(-gammas*(xn-c)))

            if show_initial_weights:
                gammas_init, c_init = np.around(self.init_weights,2)
                gammas_init, c_init = gammas_init.reshape(n_memb, n_input, 1), c_init.reshape(n_memb, n_input, 1)
                init_curves = 1 / (1 + np.exp(-gammas_init*(xn-c_init)))

        fig, axs = plt.subplots(nrows=n_input, ncols=1, figsize=(8, n_input*3))
        fig.suptitle('Membership functions', size=16)
        for n in range(n_input):
            axs[n].grid(True)
            if n >= self.n:
                axs[n].set_title(f'Control Variable {n-self.n+1}')
            else:
                axs[n].set_title(f'Input {n+1}')
            for m in range(self.m):
                axs[n].plot(xn[m,n,:], memb_curves[m,n,:])

        if show_initial_weights: # plot initial membership curve
            for n in range(n_input):
                axs[n].set_prop_cycle(None) # reset color cycle
                for m in range(self.m):
                    axs[n].plot(xn[m,n,:], init_curves[m,n,:], '--', alpha=.5)
        plt.show()


    def fit(self, X, y, **kwargs):
        # save initial weights in the anfis class
        self.init_weights = self.model.get_layer('fuzzyLayer').get_weights()

        # fit model & update weights in the anfis class
        history = self.model.fit(X,y, **kwargs)
        self.update_weights()

        # clear the graphs
        tf.keras.backend.clear_session()

        return history

    def get_memberships(self, Xs):
        intermediate_layer_model = keras.Model(inputs = self.model.input,
                                               outputs = self.model.get_layer('normLayer').output)
        intermediate_output = intermediate_layer_model.predict(Xs)

        return intermediate_output



# Custom weight initializer
def equally_spaced_initializer(shape, minval=-1.5, maxval=1.5, dtype=tf.float32):
    """
    Custom weight initializer:
        euqlly spaced weights along an operating range of [minval, maxval].
    """
    linspace = tf.reshape(tf.linspace(minval, maxval, shape[0]),
                          (-1,1))
    return tf.Variable(tf.tile(linspace, (1,shape[1])))



# Layer 1
class FuzzyLayer(keras.layers.Layer):
    def __init__(self, n_input, n_control, n_memb, memb_func='gaussian', **kwargs):
        super(FuzzyLayer, self).__init__(**kwargs)
        self.n = n_input
        self.n_control = n_control
        self.m = n_memb
        self.memb_func = memb_func

    def build(self, batch_input_shape):
        self.batch_size = batch_input_shape[0]
        if self.memb_func == 'gbellmf':
            self.a = self.add_weight(name='a',
                            shape=(self.m, self.n+self.n_control),
                            initializer = keras.initializers.RandomUniform(minval=.7, maxval=1.3, seed=1),
                            #initializer = 'ones',
                            trainable=True)
            self.b = self.add_weight(name='b',
                            shape=(self.m, self.n+self.n_control),
                            initializer = keras.initializers.RandomUniform(minval=.7, maxval=1.3, seed=1),
                            #initializer = 'ones',
                            trainable=True)
            self.c = self.add_weight(name='c',
                            shape=(self.m, self.n+self.n_control),
                            initializer = equally_spaced_initializer,
                            #initializer = keras.initializers.RandomUniform(minval=-1.5, maxval=1.5, seed=1),
                            #initializer = 'zeros',
                            trainable=True)

        elif self.memb_func == 'gaussian':
            self.mu = self.add_weight(name='mu',
                            shape=(self.m, self.n+self.n_control),
                            initializer = equally_spaced_initializer,
                            #initializer = keras.initializers.RandomUniform(minval=-1.5, maxval=1.5, seed=1),
                            #initializer = 'zeros',
                            trainable=True)
            self.sigma = self.add_weight(name='sigma',
                            shape=(self.m, self.n+self.n_control),
                            initializer = keras.initializers.RandomUniform(minval=.7, maxval=1.3, seed=1),
                            #initializer = 'ones',
                            trainable=True)

        elif self.memb_func == 'sigmoid':
            self.gamma = self.add_weight(name = 'gamma',
                            shape=(self.m, self.n+self.n_control),
                            initializer = equally_spaced_initializer, #'ones',
                            trainable = True)

            self.c = self.add_weight(name = 'c',
                            shape=(self.m, self.n+self.n_control),
                            initializer = equally_spaced_initializer, #'ones',
                            trainable = True)

        super(FuzzyLayer, self).build(batch_input_shape)  # Be sure to call this at the end

    def call(self, x_inputs):
        if self.memb_func == 'gbellmf':
            Layer1 = 1/(1+
                   tf.math.pow(
                        tf.square(tf.subtract(
                           tf.reshape(
                               tf.tile(x_inputs, (1, self.m)), (-1, self.m, self.n+self.n_control))
                           ,self.c
                           ) / self.a)
                        , self.b)
                       )
        elif self.memb_func == 'gaussian':
            Layer1 = tf.exp(-1*
                tf.square(tf.subtract(
                    tf.reshape(
                        tf.tile(x_inputs, (1, self.m)), (-1, self.m, self.n+self.n_control))
                    ,self.mu
                    )) / tf.square(self.sigma))

        elif self.memb_func == 'sigmoid':
            Layer1 = tf.math.divide(1,
                        tf.math.exp(-self.gamma*
                            tf.subtract(
                               tf.reshape(
                                   tf.tile(x_inputs, (1, self.m)), (-1, self.m, self.n+self.n_control))
                                            ,self.c)
                                    )
                                    )
        return Layer1  # = fuzzy cluster

    def compute_output_shape(self, batch_input_shape):
        # return ((self.batch_size, self.m, self.n+self.n_control))
        return tf.TensorShape([self.batch_size, self.m, self.n+self.n_control])

# Layer 2
class RuleLayer(keras.layers.Layer):
    def __init__(self, n_input, n_control, n_memb, **kwargs):
        super(RuleLayer, self).__init__( **kwargs)
        self.n = n_input
        self.n_control = n_control
        self.m = n_memb
        self.batch_size = None

    def build(self, batch_input_shape):
        self.batch_size = batch_input_shape[0]
        # self.batch_size = tf.shape(batch_input_shape)[0]
        super(RuleLayer, self).build(batch_input_shape)  # Be sure to call this at the end

    def call(self, input_):
        CP = []
        # a tensor object is not assignable*, so you cannot use it on the left-hand side of an assignment.
        # build a Python list of tensors, and tf.stack() them together at the end of the loop:
        for batch in range(self.batch_size):
            xd_shape = [self.m]
            c_shape = [1]
            cp = input_[batch,:,0]

            for d in range(1,self.n+self.n_control):
                # append shape indizes
                c_shape.insert(0,self.m)
                xd_shape.insert(0,1)
                # get cartesian product for each dimension
                xd = tf.reshape(input_[batch,:,d], (xd_shape))
                c = tf.reshape(cp,(c_shape))
                cp = tf.matmul(c , xd)

            flat_cp = tf.reshape(cp,(1, self.m**(self.n+self.n_control)))
            CP.append(flat_cp)

        return tf.reshape(tf.stack(CP), (self.batch_size, self.m**(self.n+self.n_control)))

    def compute_output_shape(self, batch_input_shape):
        if (self.n+self.n_control) == 1:
            return tf.TensorShape([self.batch_size, self.m])
        else:
            return tf.TensorShape([self.batch_size, self.m** (self.n+self.n_control)])

# Layer 3
class NormLayer(keras.layers.Layer):
    def __init__(self, **kwargs):
        super().__init__( **kwargs)

    def call(self, fire):
        w_sum = tf.reshape(tf.reduce_sum(fire, axis=1), (-1,1))
        w_norm = fire / w_sum
        return w_norm

    def compute_output_shape(self, batch_input_shape):
        return batch_input_shape

# Layer 4
class DefuzzLayer(keras.layers.Layer):
    def __init__(self, n_input, n_control, n_memb, **kwargs):
        super().__init__( **kwargs)
        self.n = n_input
        self.n_control = n_control
        self.m = n_memb

    def build(self, batch_input_shape):
        self.CP_bias = self.add_weight(name='Consequence_bias',
                                                 shape=(1, self.m **(self.n+self.n_control)),
                                                 initializer = keras.initializers.RandomUniform(minval=-2, maxval=2),
                                                 # initializer = 'ones',
                                                 trainable=True)
        self.CP_weight = self.add_weight(name='Consequence_weight',
                                            shape=(self.n, self.m **(self.n+self.n_control)),
                                            initializer = keras.initializers.RandomUniform(minval=-2, maxval=2),
                                            # initializer = 'ones',
                                            trainable=True)

    def call(self, w_norm, Xs):

        Layer4=tf.multiply(w_norm,
                           tf.matmul(Xs, self.CP_weight) + self.CP_bias)
        return Layer4  # Defuzzyfied Layer

    def compute_output_shape(self, batch_input_shape):
        return batch_input_shape

# Layer 5
class SummationLayer(keras.layers.Layer):
    def __init__(self, **kwargs):
        super().__init__( **kwargs)

    def build(self, batch_input_shape):
        self.batch_size = batch_input_shape[0]
        #self.batch_size = tf.shape(batch_input_shape)[0]
        super(SummationLayer, self).build(batch_input_shape)  # Be sure to call this at the end

    def call(self, Layer4):
        output = tf.reduce_sum(Layer4, axis=1)
        output = tf.reshape(output, (self.batch_size, 1))
        return output # final output

    def compute_output_shape(self, batch_input_shape):
        return tf.TensorShape([self.batch_size,1])


#########################################################################################

# EXAMPLE
if __name__ == "__main__":
    # set parameters
    param = fis_parameters(
            n_input = 2,                # no. of Regressors
            n_control = 1,              # no. of control Variables
            n_memb = 2,                 # no. of fuzzy memberships
            batch_size = 16,            # 16 / 32 / 64 / ...
            memb_func = 'sigmoid',      # 'gaussian' / 'gbellmf' / 'sigmoid'
            optimizer = 'adam',          # sgd / adam / ...
            loss = 'huber_loss',               # mse / mae / huber_loss / mean_absolute_percentage_error / ...
            n_epochs = 100               # 10 / 25 / 50 / 100 / ...
            )
    # create random data
    X_data_train = np.random.rand(param.batch_size*5, param.n_input)
    X_data_test = np.random.rand(param.batch_size*2, param.n_input)

    X_control_train = np.random.rand(param.batch_size*5, 1)
    X_control_test = np.random.rand(param.batch_size*2, 1)

    X_train = np.concatenate((X_data_train, X_control_train),axis=1)
    X_test = np.concatenate((X_data_test, X_control_test),axis=1)

    y_train = np.random.rand(param.batch_size*5, 1)
    y_test = np.random.rand(param.batch_size*2, 1)

    fis = CONANFIS(n_input = param.n_input,
                n_control = param.n_control,
                n_memb = param.n_memb,
                batch_size = param.batch_size,
                memb_func = param.memb_func,
                name = 'myanfis'
                )

    # compile model
    fis.model.compile(optimizer=param.optimizer,
                      loss=param.loss
                      #,metrics=['mse']  # ['mae', 'mse']
                      )

    # fit model
    history = fis.fit(X_train, y_train,
                      epochs=param.n_epochs,
                      batch_size=param.batch_size,
                      validation_data = (X_test, y_test),
                      # callbacks = [tensorboard_callback]  # for tensorboard
                      )

    # eval model
    import pandas as pd
    fis.plotmfs(show_initial_weights=True)

    loss_curves = pd.DataFrame(history.history)
    loss_curves.plot(figsize=(8, 5))

    fis.model.summary()

    # get premise parameters
    premise_parameters = fis.model.get_layer('fuzzyLayer').get_weights()       # alternative

    # get consequence paramters
    bias = fis.bias
    weights = fis.weights
    # conseq_parameters = fis.model.get_layer('defuzzLayer').get_weights()       # alternative





####  manually check ANFIS Layers step-by-step

    # L1 = myanfis.FuzzyLayer(n_input, n_memb)
    # L1(X) # to call build function
    # mus = fis.mus
    # sigmas = fis.sigmas
    # L1.set_weights([fis.mus, fis.sigmas])

    # op1 = np.array(L1(Xs))

    # L2 = myanfis.RuleLayer(n_input, n_memb)
    # op2 = np.array(L2(op1))

    # L3 = myanfis.NormLayer()
    # op3 = np.array(L3(op2))

    # L4 = myanfis.DefuzzLayer(n_input, n_memb)
    # L4(op3, Xs) # to call build function
    # bias = fis.bias
    # weights = fis.weights
    # L4.set_weights([fis.bias, fis.weights])
    # op4 = np.array(L4(op3, Xs))

    # L5 = myanfis.SummationLayer()
    # op5 = np.array(L5(op4))