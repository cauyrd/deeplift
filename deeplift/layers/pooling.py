from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from .core import *
from .helper_functions import conv1d_transpose_via_conv2d
from . import helper_functions as hf

class Pool1D(SingleInputMixin, Node):

    def __init__(self, pool_length, strides, padding_mode, **kwargs):
        super(Pool1D, self).__init__(**kwargs) 
        self.pool_length = pool_length
        if (hasattr(strides, '__iter__')):
            assert len(strides)==1
            strides=strides[0]
        self.strides = strides
        self.padding_mode = padding_mode

    def _compute_shape(self, input_shape):
        shape_to_return = [None] 
        if (self.padding_mode != PaddingMode.valid):
            raise RuntimeError("Please implement shape inference for"
                               " padding mode: "+str(self.padding_mode))
        #assuming that overhangs are excluded
        shape_to_return.append(1+
            int((input_shape[1]-self.pool_length)/self.strides)) 
        shape_to_return.append(input_shape[-1]) #channels unchanged
        return shape_to_return

    def _get_mxts_increments_for_inputs(self):
        raise NotImplementedError()


class MaxPool1D(Pool1D):
    """
    Heads-up: an all-or-none MaxPoolDeepLiftMode is only 
        appropriate when all inputs falling within a single
        kernel have the same default value.
    Heads-up: scaled all-or-none MaxPoolDeepLiftMode can
        lead to odd results if the inputs falling within a
        single kernel don't have approx even default vals
    """ 
    def __init__(self, maxpool_deeplift_mode, **kwargs):
        super(MaxPool1D, self).__init__(**kwargs) 
        self.maxpool_deeplift_mode = maxpool_deeplift_mode

    def _build_activation_vars(self, input_act_vars):
        return tf.squeeze(
                tf.nn.max_pool(value=tf.expand_dims(input_act_vars,1),
                     ksize=(1,1,self.pool_length,1),
                     strides=(1,1,self.strides,1),
                     padding=self.padding_mode),1)

    def _build_pos_and_neg_contribs(self):
        if (self.verbose):
            print("Heads-up: current implementation assumes maxpool layer "
                  "is followed by a linear transformation (conv/dense layer)")
        #placeholder; not used for linear layer, hence assumption above
        return tf.zeros_like(tensor=self.get_activation_vars(),
                      name="dummy_pos_cont_"+str(self.get_name())),\
               tf.zeros_like(tensor=self.get_activation_vars(),
                      name="dummy_neg_cont_"+str(self.get_name()))

    def _grad_op(self, out_grad):
        return tf.squeeze(tf.nn._nn_grad.gen_nn_ops._max_pool_grad(
                orig_input=tf.expand_dims(self._get_input_activation_vars(),1),
                orig_output=tf.expand_dims(self.get_activation_vars(),1),
                grad=tf.expand_dims(out_grad,1),
                ksize=(1,1,self.pool_length,1),
                strides=(1,1,self.strides,1),
                padding=self.padding_mode),1)

    def _get_mxts_increments_for_inputs(self):
        if (self.maxpool_deeplift_mode==MaxPoolDeepLiftMode.gradient):
            pos_mxts_increments = self._grad_op(self.get_pos_mxts())
            neg_mxts_increments = self._grad_op(self.get_neg_mxts())
        else:
            raise RuntimeError("Unsupported maxpool_deeplift_mode: "+
                               str(self.maxpool_deeplift_mode))
        return pos_mxts_increments, neg_mxts_increments
            

class AvgPool1D(Pool1D):

    def __init__(self, **kwargs):
        super(AvgPool1D, self).__init__(**kwargs) 

    def _build_activation_vars(self, input_act_vars):
        return tf.squeeze(
                tf.nn.avg_pool(value=tf.expand_dims(input_act_vars,1),
                 ksize=(1,1,self.pool_length,1),
                 strides=(1,1,self.strides,1),
                 padding=self.padding_mode),1)

    def _build_pos_and_neg_contribs(self):
        inp_pos_contribs, inp_neg_contribs =\
            self._get_input_pos_and_neg_contribs()
        pos_contribs = self._build_activation_vars(inp_pos_contribs)
        neg_contribs = self._build_activation_vars(inp_neg_contribs) 
        return pos_contribs, neg_contribs

    def _grad_op(self, out_grad):
        return tf.squeeze(tf.nn._nn_grad.gen_nn_ops._avg_pool_grad(
            orig_input_shape=
                tf.shape(tf.expand_dims(self._get_input_activation_vars(),1)),
            grad=tf.expand_dims(out_grad,1),
            ksize=(1,1,self.pool_length,1),
            strides=(1,1,self.strides,1),
            padding=self.padding_mode),1)

    def _get_mxts_increments_for_inputs(self):
        pos_mxts_increments = self._grad_op(self.get_pos_mxts())
        neg_mxts_increments = self._grad_op(self.get_neg_mxts())
        return pos_mxts_increments, neg_mxts_increments 


class Pool2D(SingleInputMixin, Node):

    def __init__(self, pool_size, strides, padding_mode, **kwargs):
        super(Pool2D, self).__init__(**kwargs) 
        self.pool_size = pool_size 
        self.strides = strides
        self.padding_mode = padding_mode

    def get_yaml_compatible_object_kwargs(self):
        kwargs_dict = super(Pool2D, self).\
                       get_yaml_compatible_object_kwargs()
        kwargs_dict['pool_size'] = self.pool_size
        kwargs_dict['strides'] = self.strides
        kwargs_dict['padding_mode'] = self.padding_mode
        return kwargs_dict

    def _compute_shape(self, input_shape):
        shape_to_return = [None] #num channels unchanged 
        if (self.padding_mode != PaddingMode.valid):
            raise RuntimeError("Please implement shape inference for"
                               " padding mode: "+str(self.padding_mode))
        for (dim_inp_len, dim_kern_width, dim_stride) in\
            zip(input_shape[1:3], self.pool_size, self.strides):
            #assuming that overhangs are excluded
            shape_to_return.append(
             1+int((dim_inp_len-dim_kern_width)/dim_stride)) 
        shape_to_return.append(input_shape[-1])
        return shape_to_return

    def _get_mxts_increments_for_inputs(self):
        raise NotImplementedError()


class MaxPool2D(Pool2D):
    """
    Heads-up: an all-or-none MaxPoolDeepLiftMode is only 
        appropriate when all inputs falling within a single
        kernel have the same default value.
    Heads-up: scaled all-or-none MaxPoolDeepLiftMode can
        lead to odd results if the inputs falling within a
        single kernel don't have approx even default vals
    """ 
    def __init__(self, maxpool_deeplift_mode,
                       **kwargs):
        super(MaxPool2D, self).__init__(**kwargs) 
        self.maxpool_deeplift_mode = maxpool_deeplift_mode

    def _build_activation_vars(self, input_act_vars):
        return tf.nn.max_pool(value=input_act_vars,
                             ksize=(1,)+self.pool_size+(1,),
                             strides=(1,)+self.strides+(1,),
                             padding=self.padding_mode)

    def _build_pos_and_neg_contribs(self):
        if (self.verbose):
            print("Heads-up: current implementation assumes maxpool layer "
                  "is followed by a linear transformation (conv/dense layer)")
        #placeholder; not used for linear layer, hence assumption above
        return tf.zeros_like(tensor=self.get_activation_vars(),
                      name="dummy_pos_cont_"+str(self.get_name())),\
               tf.zeros_like(tensor=self.get_activation_vars(),
                      name="dummy_neg_cont_"+str(self.get_name()))

    def _grad_op(self, out_grad):
        return tf.nn._nn_grad.gen_nn_ops._max_pool_grad(
                orig_input=self._get_input_activation_vars(),
                orig_output=self.get_activation_vars(),
                grad=out_grad,
                ksize=(1,)+self.pool_size+(1,),
                strides=(1,)+self.strides+(1,),
                padding=self.padding_mode)

    def _get_mxts_increments_for_inputs(self):
        if (self.maxpool_deeplift_mode==MaxPoolDeepLiftMode.gradient):
            pos_mxts_increments = self._grad_op(self.get_pos_mxts())
            neg_mxts_increments = self._grad_op(self.get_neg_mxts())
        else:
            raise RuntimeError("Unsupported maxpool_deeplift_mode: "+
                               str(self.maxpool_deeplift_mode))
        return pos_mxts_increments, neg_mxts_increments

    def _get_mxts_increments_for_inputs(self):
        if (self.maxpool_deeplift_mode==MaxPoolDeepLiftMode.gradient):
            pos_mxts_increments = self._grad_op(self.get_pos_mxts())
            neg_mxts_increments = self._grad_op(self.get_neg_mxts())
        else:
            raise RuntimeError("Unsupported maxpool_deeplift_mode: "+
                               str(self.maxpool_deeplift_mode))
        return pos_mxts_increments, neg_mxts_increments
            

class AvgPool2D(Pool2D):

    def __init__(self, **kwargs):
        super(AvgPool2D, self).__init__(**kwargs) 

    def _build_activation_vars(self, input_act_vars):
        return tf.nn.avg_pool(value=input_act_vars,
                             ksize=(1,)+self.pool_size+(1,),
                             strides=(1,)+self.strides+(1,),
                             padding=self.padding_mode)

    def _build_pos_and_neg_contribs(self):
        inp_pos_contribs, inp_neg_contribs =\
            self._get_input_pos_and_neg_contribs()
        pos_contribs = self._build_activation_vars(inp_pos_contribs)
        neg_contribs = self._build_activation_vars(inp_neg_contribs) 
        return pos_contribs, neg_contribs

    def _grad_op(self, out_grad):
        return tf.nn._nn_grad.gen_nn_ops._avg_pool_grad(
            orig_input_shape=tf.shape(self._get_input_activation_vars()),
            grad=out_grad,
            ksize=(1,)+self.pool_size+(1,),
            strides=(1,)+self.strides+(1,),
            padding=self.padding_mode)

    def _get_mxts_increments_for_inputs(self):
        pos_mxts_increments = self._grad_op(self.get_pos_mxts())
        neg_mxts_increments = self._grad_op(self.get_neg_mxts())
        return pos_mxts_increments, neg_mxts_increments 