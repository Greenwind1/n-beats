import os
from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np

from data import dummy_data_generator_multivariate, get_m4_data_multivariate, get_nrj_data, get_kcg_data
from model import NBeatsNet


np.random.seed(0)

GENERIC_BLOCK = 'generic'
TREND_BLOCK = 'trend'
SEASONALITY_BLOCK = 'seasonality'
    
    
def get_script_arguments():
    parser = ArgumentParser()
    parser.add_argument('--task', choices=['m4', 'kcg', 'nrj', 'dummy'], required=True)
    parser.add_argument('--test', action='store_true')
    return parser.parse_args()


def get_metrics(y_true, y_hat):
    error = np.mean(np.square(y_true - y_hat))
    smape = np.mean(2 * np.abs(y_true - y_hat) / (np.abs(y_true) + np.abs(y_hat)))
    return smape, error


def ensure_results_dir():
    if not os.path.exists('results/test'):
        os.makedirs('results/test')


def generate_data(backcast_length, forecast_length):
    def gen(num_samples):
        return next(dummy_data_generator_multivariate(backcast_length, forecast_length,
                                         signal_type='seasonality', random=True,
                                         batch_size=num_samples))

    x_train, y_train = gen(6_000)
    x_test, y_test = gen(1_000)
    return x_train.reshape((x_train.shape[0], x_train.shape[1], 1)), None, y_train.reshape((y_train.shape[0], y_train.shape[1], 1)), x_test.reshape((x_test.shape[0], x_test.shape[1], 1)), None, y_test.reshape((y_test.shape[0], y_test.shape[1], 1))


def train_model(model: NBeatsNet, task: str):
    ensure_results_dir()

    if task == 'dummy':
        x_train, e_train, y_train, x_test, e_test, y_test = generate_data(model.backcast_length, model.forecast_length)
    elif task == 'm4':
        x_test, e_test, y_test = get_m4_data_multivariate(model.backcast_length, model.forecast_length, is_training=False)
    elif task == 'kcg':
        x_test, e_test, y_test = get_kcg_data(model.backcast_length, model.forecast_length, is_training=False)
    elif task == 'nrj':
        x_test, e_test, y_test = get_nrj_data(model.backcast_length, model.forecast_length, is_training=False)
    else:
        raise Exception('Unknown task.')

    print('x_test.shape=', x_test.shape)  

    for step in range(model.steps):
        if task == 'm4':
            x_train, e_train, y_train = get_m4_data_multivariate(model.backcast_length, model.forecast_length, is_training=True)
        if task == 'kcg':
            x_train, e_train, y_train = get_kcg_data(model.backcast_length, model.forecast_length, is_training=True)
        if task == 'nrj':
            x_train, e_train, y_train = get_nrj_data(model.backcast_length, model.forecast_length, is_training=True)            
        
        if model.exo_dim > 0:
            model.train_on_batch([x_train, e_train], y_train)
        else:
            model.train_on_batch(x_train, y_train)
        
        if step % model.plot_results == 0:
            print('step=', step)
            model.save('results/n_beats_model_' + str(step) + '.h5')
            if model.exo_dim > 0:
                predictions = model.predict([x_train, e_train])
                validation_predictions = model.predict([x_test, e_test])
            else:
                predictions = model.predict(x_train)
                validation_predictions = model.predict(x_test)
            smape = get_metrics(y_test, validation_predictions)[0]
            print('smape=', smape)
            if smape < model.best_perf:
                model.best_perf = smape
                model.save('results/n_beats_model_ongoing.h5')
            for l in range(model.input_dim):
                plot_keras_model_predictions(model, False, step, x_train[0, :, l], y_train[0, :, l], predictions[0, :, l], axis=l)
                plot_keras_model_predictions(model, True, step, x_test[0, :, l], y_test[0, :, l], validation_predictions[0, :, l], axis=l)

    model.nbeats.save('results/n_beats_model.h5')

    if model.exo_dim > 0:
        predictions = model.predict([x_train, e_train])
        validation_predictions = model.predict([x_test, e_test])
    else:
        predictions = model.predict(x_train)
        validation_predictions = model.predict(x_test)

    for l in range(model.input_dim):
        plot_keras_model_predictions(model, False, model.steps, x_train[10, :, l], y_train[10, :, l], predictions[10, :, l], axis=l)
        plot_keras_model_predictions(model, True, model.steps, x_test[10, :, l], y_test[10, :, l], validation_predictions[10, :, l], axis=l)
    print('smape=', get_metrics(y_test, validation_predictions)[0])
    print('error=', get_metrics(y_test, validation_predictions)[1])


def plot_keras_model_predictions(model, is_test, step, backcast, forecast, prediction, axis):
    legend = ['backcast', 'forecast', 'predictions of forecast']
    if is_test:
        title = 'results/test/' + 'step_' + str(step) + '_axis_' + str(axis) + '.png'
    else:
        title = 'results/' + 'step_' + str(step) + '_axis_' + str(axis) + '.png'
    plt.figure()
    plt.grid(True)
    x_y = np.concatenate([backcast, forecast], axis=-1).flatten()
    plt.plot(list(range(model.backcast_length)), backcast.flatten(), color='b')
    plt.plot(list(range(len(x_y) - model.forecast_length, len(x_y))), forecast.flatten(), color='g')
    plt.plot(list(range(len(x_y) - model.forecast_length, len(x_y))), prediction.flatten(), color='r')
    plt.scatter(range(len(x_y)), x_y.flatten(), color=['b'] * model.backcast_length + ['g'] * model.forecast_length)
    plt.scatter(list(range(len(x_y) - model.forecast_length, len(x_y))), prediction.flatten(), color=['r'] * model.forecast_length)
    plt.legend(legend)
    plt.savefig(title)
    plt.close()
        
        
def main():
    args = get_script_arguments()

    # m4
    if args.task == 'm4' or if args.task == 'dummy':
        model = NBeatsNet(input_dim=1, exo_dim=0, backcast_length=10, forecast_length=1, 
                          stack_types=[GENERIC_BLOCK, GENERIC_BLOCK], nb_blocks_per_stack=2, 
                          thetas_dim = [4, 4], share_weights_in_stack=False,
                          hidden_layer_units=128,
                          learning_rate=1e-6, 
                          loss='mae', 
                          steps=1001, 
                          best_perf=100., 
                          plot_results=1
                          )
    
    #kcg
    if args.task == 'kcg':
        model = NBeatsNet(input_dim=2, exo_dim=0, backcast_length=360, forecast_length=10, 
                          stack_types=[TREND_BLOCK, SEASONALITY_BLOCK], nb_blocks_per_stack=3, 
                          thetas_dim = [4, 8], share_weights_in_stack=False,
                          hidden_layer_units=256,
                          learning_rate=1e-5, 
                          loss='mae', 
                          steps=10001, 
                          best_perf=100., 
                          plot_results=10
                          )

    #nrj
    if args.task == 'nrj':
        model = NBeatsNet(input_dim=1, exo_dim=2, backcast_length=10, forecast_length=1, 
                          stack_types=[TREND_BLOCK, SEASONALITY_BLOCK], nb_blocks_per_stack=2, 
                          thetas_dim = [4, 8], share_weights_in_stack=False,
                          hidden_layer_units=128,
                          learning_rate=1e-7, 
                          loss='mae', 
                          steps=100001, 
                          best_perf=100., 
                          plot_results=100
                          )   
    
    model.compile_model()
    if args.test:
        model.steps = 5
    train_model(model, args.task)

if __name__ == '__main__':
    main()
