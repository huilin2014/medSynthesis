import tensorflow as tf
import numpy as np


def lp_loss(ct_generated, gt_ct, l_num, batch_size_tf):
    """
    Calculates the sum of lp losses between the predicted and ground truth frames.

    @param ct_generated: The predicted ct
    @param gt_ct: The ground truth ct
    @param l_num: 1 or 2 for l1 and l2 loss, respectively).

    @return: The lp loss.
    """
    lp_loss=tf.reduce_sum(tf.abs(ct_generated - gt_ct)**l_num)/(2*tf.cast(batch_size_tf,tf.float32))
    #print 'lp_loss ',gt_ct.get_shape()
    tf.add_to_collection('losses', lp_loss)

    loss = tf.add_n(tf.get_collection('losses'), name='total_loss')
    return loss



def cross_entropy_Discriminator(logits_D,gt_D):
    """
    logits_D is the output of the discriminator [batch_size,1]
    gt_D should be all ones for real data, and all zeros for fake-
    generated (output of generator) data[batch_size,1]"""

    bce=tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits_D, gt_D))
    return bce






def combined_loss(gen_frames, gt_frames, d_preds, lam_adv=1, lam_lp=1, lam_gdl=1, l_num=2, alpha=2):
    """
    Calculates the sum of the combined adversarial, lp and GDL losses in the given proportion. Used
    for training the generative model.

    @param gen_frames: A list of tensors of the generated frames at each scale.
    @param gt_frames: A list of tensors of the ground truth frames at each scale.
    @param d_preds: A list of tensors of the classifications made by the discriminator model at each
                    scale.
    @param lam_adv: The percentage of the adversarial loss to use in the combined loss.
    @param lam_lp: The percentage of the lp loss to use in the combined loss.
    @param lam_gdl: The percentage of the GDL loss to use in the combined loss.
    @param l_num: 1 or 2 for l1 and l2 loss, respectively).
    @param alpha: The power to which each gradient term is raised in GDL loss.

    @return: The combined adversarial, lp and GDL losses.
    """
    batch_size = tf.shape(gen_frames[0])[0]  # variable batch size as a tensor

    loss = lam_lp * lp_loss(gen_frames, gt_frames, l_num)
    loss += lam_gdl * gdl_loss(gen_frames, gt_frames, alpha)
    if c.ADVERSARIAL: loss += lam_adv * adv_loss(d_preds, tf.ones([batch_size, 1]))

    return loss


def bce_loss(preds, targets):
    """
    Calculates the sum of binary cross-entropy losses between predictions and ground truths.

    @param preds: A 1xN tensor. The predicted classifications of each frame.
    @param targets: A 1xN tensor The target labels for each frame. (Either 1 or -1). Not "truths"
                    because the generator passes in lies to determine how well it confuses the
                    discriminator.

    @return: The sum of binary cross-entropy losses.
    """
    return tf.squeeze(-1 * (tf.matmul(targets, log10(preds), transpose_a=True) +
                            tf.matmul(1 - targets, log10(1 - preds), transpose_a=True)))


def gdl3d_loss(gen_frames, gt_frames, alpha):
    """
    Calculates the sum of GDL losses between the predicted and ground truth frames.
    This is the 3d version.

    @param gen_frames: The predicted frames at each scale.
    @param gt_frames: The ground truth frames at each scale
    @param alpha: The power to which each gradient term is raised.

    @return: The GDL loss for 3d. Dong
    """
    # calculate the loss for each scale
    scale_losses = []
    for i in xrange(len(gen_frames)):
        # create filters [-1, 1] and [[1],[-1]] for diffing to the left and down respectively.
        pos = tf.constant(np.identity(1), dtype=tf.float32)
        neg = -1 * pos

        baseFilter = tf.pack([tf.expand_dims(pos, 0), tf.expand_dims(neg, 0)])  # [[1],[-1]]# 2x1x1x1
        filter_x = tf.expand_dims(baseFilter, 1)  # [-1, 1] # 2x1x1x1x1
        filter_y = tf.expand_dims(baseFilter, 0)  # [-1, 1] # 1x2x1x1x1
        filter_z = tf.expand_dims(tf.pack([neg, pos]), 0)  # [-1, 1] # 1x2x1x1
        filter_z = tf.expand_dims(filter_z, 0) # [-1, 1] #1x1x2x1x1
        strides = [1, 1, 1, 1, 1]  # stride of (1, 1)
        padding = 'SAME'

        gen_dx = tf.abs(tf.nn.conv3d(gen_frames[i], filter_x, strides, padding=padding))
        gen_dy = tf.abs(tf.nn.conv3d(gen_frames[i], filter_y, strides, padding=padding))
        gen_dz = tf.abs(tf.nn.conv3d(gen_frames[i], filter_z, strides, padding=padding))
        gt_dx = tf.abs(tf.nn.conv3d(gt_frames[i], filter_x, strides, padding=padding))
        gt_dy = tf.abs(tf.nn.conv3d(gt_frames[i], filter_y, strides, padding=padding))
        gt_dz = tf.abs(tf.nn.conv3d(gt_frames[i], filter_z, strides, padding=padding))

        grad_diff_x = tf.abs(gt_dx - gen_dx)
        grad_diff_y = tf.abs(gt_dy - gen_dy)
        grad_diff_z = tf.abs(gt_dz - gen_dz)

        scale_losses.append(tf.reduce_sum((grad_diff_x ** alpha + grad_diff_y ** alpha + grad_diff_z ** alpha)))

    # condense into one tensor and avg
    return tf.reduce_mean(tf.pack(scale_losses))




def gdl_loss(gen_frames, gt_frames, alpha):
    """
    Calculates the sum of GDL losses between the predicted and ground truth frames.

    @param gen_frames: The predicted frames at each scale.
    @param gt_frames: The ground truth frames at each scale
    @param alpha: The power to which each gradient term is raised.

    @return: The GDL loss for 2d.
    """
    # calculate the loss for each scale
    scale_losses = []
    for i in xrange(len(gen_frames)):
        # create filters [-1, 1] and [[1],[-1]] for diffing to the left and down respectively.
        pos = tf.constant(np.identity(1), dtype=tf.float32)
        neg = -1 * pos
        filter_x = tf.expand_dims(tf.pack([neg, pos]), 0)  # [-1, 1]
        filter_y = tf.pack([tf.expand_dims(pos, 0), tf.expand_dims(neg, 0)])  # [[1],[-1]]
        strides = [1, 1, 1, 1]  # stride of (1, 1)
        padding = 'SAME'

        gen_dx = tf.abs(tf.nn.conv2d(gen_frames[i], filter_x, strides, padding=padding))
        gen_dy = tf.abs(tf.nn.conv2d(gen_frames[i], filter_y, strides, padding=padding))
        gt_dx = tf.abs(tf.nn.conv2d(gt_frames[i], filter_x, strides, padding=padding))
        gt_dy = tf.abs(tf.nn.conv2d(gt_frames[i], filter_y, strides, padding=padding))

        grad_diff_x = tf.abs(gt_dx - gen_dx)
        grad_diff_y = tf.abs(gt_dy - gen_dy)

        scale_losses.append(tf.reduce_sum((grad_diff_x ** alpha + grad_diff_y ** alpha)))

    # condense into one tensor and avg
    return tf.reduce_mean(tf.pack(scale_losses))


def adv_loss(preds, labels):
    """
    Calculates the sum of BCE losses between the predicted classifications and true labels.

    @param preds: The predicted classifications at each scale.
    @param labels: The true labels. (Same for every scale).

    @return: The adversarial loss.
    """
    # calculate the loss for each scale
    scale_losses = []
    for i in xrange(len(preds)):
        loss = bce_loss(preds[i], labels)
        scale_losses.append(loss)

    # condense into one tensor and avg
    return tf.reduce_mean(tf.pack(scale_losses))
