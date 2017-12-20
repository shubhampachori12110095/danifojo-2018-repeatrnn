from __future__ import print_function, division
import argparse
import os

import numpy as np
import tensorflow as tf
from tensorflow.contrib.rnn import static_rnn, BasicRNNCell
from act_binary_cell import ACTCell
from tqdm import trange

# Training settings
parser = argparse.ArgumentParser(description='Parity task')
parser.add_argument('--input-size', type=int, default=64, metavar='N',
                    help='input size for training (default: 64)')
parser.add_argument('--hidden-size', type=int, default=128, metavar='N',
                    help='hidden size for training (default: 128)')
parser.add_argument('--batch-size', type=int, default=128, metavar='N',
                    help='input batch size for training (default: 128)')
parser.add_argument('--steps', type=int, default=16000000, metavar='N',
                    help='number of args.steps to train (default: 16000000)')
parser.add_argument('--log-interval', type=int, default=100, metavar='N',
                    help='how many steps between each checkpoint (default: 100)')
parser.add_argument('--start-step', default=0, type=int, metavar='N',
                    help='manual step number (useful on restarts) (default: 0)')
parser.add_argument('--lr', type=float, default=0.0001, metavar='LR',
                    help='learning rate (default: 0.0001)')
parser.add_argument('--tau', type=float, default=1e-3, metavar='TAU',
                    help='value of the time penalty tau (default: 0.001)')
parser.add_argument('--resume', default='', type=str, metavar='PATH',
                    help='path to latest checkpoint (default: none)')
parser.add_argument('--dont-use-act', dest='use_act', action='store_false',
                    help='whether to use act ')


def generate(args):
    x = np.random.randint(3, size=(args.batch_size, args.input_size)) - 1
    y = np.zeros((args.batch_size,))
    for i in range(args.batch_size):
        unique, counts = np.unique(x[i, :], return_counts=True)
        try:
            y[i] = dict(zip(unique, counts))[1] % 2
        except:
            y[i] = 0
    return x.astype(float), y.astype(float).reshape(-1, 1)


def main():
    args = parser.parse_args()
    input_size = args.input_size
    batch_size = args.batch_size
    hidden_size = args.hidden_size
    use_act = args.use_act

    # Placeholders for inputs.
    x = tf.placeholder(tf.float32, [batch_size, input_size])
    inputs = [x]
    y = tf.placeholder(tf.float32, [batch_size, 1])
    zeros = tf.zeros([batch_size, 1])

    rnn = BasicRNNCell(args.hidden_size)
    if use_act:
        act = ACTCell(num_units=hidden_size, cell=rnn, epsilon=0.05, max_computation=100, batch_size=batch_size)
        outputs, final_state = static_rnn(act, inputs, dtype=tf.float32)
    else:
        outputs, final_state = static_rnn(rnn, inputs, dtype=tf.float32)

    output = tf.reshape(tf.concat(outputs, 1), [-1, hidden_size])
    softmax_w = tf.get_variable("softmax_w", [hidden_size, 1])
    softmax_b = tf.get_variable("softmax_b", [1])
    logits = tf.matmul(output, softmax_w) + softmax_b

    loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(labels=y, logits=logits))

    if use_act:
        ponder = act.calculate_ponder_cost()
        tf.summary.scalar('Ponder', ponder)
        loss += args.tau*ponder

    train_step = tf.train.AdamOptimizer(args.lr).minimize(loss)

    correct_prediction = tf.equal(tf.cast(tf.greater(logits, zeros), tf.float32), y)
    accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))
    tf.summary.scalar('Accuracy', accuracy)
    tf.summary.scalar('Loss', loss)

    merged = tf.summary.merge_all()
    logdir = './logs/parity_Tau={}_Len={}'.format(args.tau, args.input_size)
    while os.path.isdir(logdir):
        logdir += '_'
    writer = tf.summary.FileWriter(logdir)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        loop = trange(args.steps)
        for i in loop:
            batch = generate(args)

            if i % args.log_interval == 0:
                if use_act:
                    summary, step_accuracy, step_loss, step_ponder \
                            = sess.run([merged, accuracy, loss, ponder], feed_dict={x: batch[0], y: batch[1]})

                    loop.set_postfix(Loss='{:0.3f}'.format(step_loss),
                                     Accuracy='{:0.3f}'.format(step_accuracy),
                                     Ponder='{:0.3f}'.format(step_ponder))
                else:
                    summary, step_accuracy, step_loss = sess.run([merged, accuracy, loss],
                                                                              feed_dict={
                                                                                  x: batch[0], y: batch[1]})

                    loop.set_postfix(Loss='{:0.3f}'.format(step_loss),
                                     Accuracy='{:0.3f}'.format(step_accuracy))
                writer.add_summary(summary, i)
            train_step.run(feed_dict={x: batch[0], y: batch[1]})


if __name__ == '__main__':
    main()





