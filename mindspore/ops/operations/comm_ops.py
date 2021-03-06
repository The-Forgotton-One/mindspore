# Copyright 2020 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

"""comm_ops"""

from ..._checkparam import ParamValidator as validator
from ...communication.management import get_rank, get_group_size, GlobalComm, get_group
from ...common import dtype as mstype
from ..primitive import PrimitiveWithInfer, prim_attr_register


class ReduceOp:
    """
    Operation options for reduce tensors.

    There are four kinds of operation options, "SUM","MAX","MIN","PROD".

        - SUM: Take the sum.
        - MAX: Take the maximum.
        - MIN: Take the minimum.
        - PROD: Take the product.
    """
    SUM = "sum"
    MAX = "max"
    MIN = "min"
    PROD = "prod"


class AllReduce(PrimitiveWithInfer):
    """
    Reduces the tensor data across all devices in such a way that all devices will get the same final result.

    Note:
        The operation of AllReduce does not support "prod" currently.
        The input of AllReduce does not support dtype "Bool".
        Tensor must have same shape and format in all processes participating in the collective.

    Args:
        op (str): Specifies an operation used for element-wise reductions,
                  like sum, max, min. Default: ReduceOp.SUM.
        group (str): The communication group to work on. Default: "hccl_world_group".

    Raises:
        TypeError: If any of op and group is not a string
                   or fusion is not a integer or the input's dtype is bool.
        ValueError: If op is "prod"

    Inputs:
        - **input_x** (Tensor) - The shape of tensor is :math:`(x_1, x_2, ..., x_R)`.

    Outputs:
        Tensor, has the same shape of the input, i.e., :math:`(x_1, x_2, ..., x_R)`.
        The contents depend on the specified operation.

    Examples:
        >>> from mindspore.communication.management import init
        >>> init('nccl')
        >>> class Net(nn.Cell):
        >>>     def __init__(self):
        >>>         super(Net, self).__init__()
        >>>         self.allreduce_sum = AllReduce(ReduceOp.SUM, group="nccl_world_group")
        >>>
        >>>     def construct(self, x):
        >>>         return self.allreduce_sum(x)
        >>>
        >>> input_ = Tensor(np.ones([2, 8]).astype(np.float32))
        >>> net = Net()
        >>> output = net(input_)
    """

    @prim_attr_register
    def __init__(self, op=ReduceOp.SUM, group=GlobalComm.WORLD_COMM_GROUP):
        if not isinstance(op, type(ReduceOp.SUM)):
            raise TypeError("The operation of AllReduce should be str.")
        if op == ReduceOp.PROD:
            raise RuntimeError("The operation of AllReduce 'prod' is not supported yet.")
        if not isinstance(get_group(group), str):
            raise TypeError("The group of AllReduce should be str.")
        self.op = op
        self.add_prim_attr('group', get_group(group))
        self.add_prim_attr('fusion', 0)

    def vm_impl(self, x):
        """Implement by vm mode."""
        x = x.asnumpy()
        return Tensor(x)

    def infer_shape(self, x_shape):
        return x_shape

    def infer_dtype(self, x_dtype):
        if x_dtype == mstype.bool_:
            raise TypeError("AllReduce does not support 'Bool' as the dtype of input!")
        return x_dtype


class AllGather(PrimitiveWithInfer):
    """
    Gathers tensors from the specified communication group.

    Note:
        Tensor must have the same shape and format in all processes participating in the collective.

    Args:
        group (str): The communication group to work on. Default: "hccl_world_group".

    Raises:
        TypeError: If group is not a string.
        ValueError: If the local rank id of the calling process in the group
                    is larger than the group's rank size.

    Inputs:
        - **input_x** (Tensor) - The shape of tensor is :math:`(x_1, x_2, ..., x_R)`.

    Outputs:
        Tensor. If the number of devices in the group is N,
        then the shape of output is :math:`(N, x_1, x_2, ..., x_R)`.

    Examples:
        >>> from mindspore.communication.management import init
        >>> init('nccl')
        >>> class Net(nn.Cell):
        >>>     def __init__(self):
        >>>         super(Net, self).__init__()
        >>>         self.allgather = AllGather(group="nccl_world_group")
        >>>
        >>>     def construct(self, x):
        >>>         return self.allgather(x)
        >>>
        >>> input_ = Tensor(np.ones([2, 8]).astype(np.float32))
        >>> net = Net()
        >>> output = net(input_)
    """

    @prim_attr_register
    def __init__(self, group=GlobalComm.WORLD_COMM_GROUP):
        if not isinstance(get_group(group), str):
            raise TypeError("The group of AllGather should be str.")
        self.rank = get_rank(get_group(group))
        self.rank_size = get_group_size(get_group(group))
        if self.rank >= self.rank_size:
            raise ValueError("The rank of AllGather should be less than the rank_size.")
        self.add_prim_attr('rank_size', self.rank_size)
        self.add_prim_attr('group', get_group(group))

    def infer_shape(self, x_shape):
        x_shape[0] = x_shape[0] * self.rank_size
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype

    def __call__(self, tensor):
        raise NotImplementedError


class ReduceScatter(PrimitiveWithInfer):
    """
     Reduces and scatters tensors from the specified communication group.

    Note:
        The back propagation of the op is not surported yet. Stay tuned for more.
        Tensor must have the same shape and format in all processes participating in the collective.
    Args:
        op (str): Specifies an operation used for element-wise reductions,
                  like sum, max, avg. Default: ReduceOp.SUM.
        group (str): The communication group to work on. Default: "hccl_world_group".

    Raises:
        TypeError: If any of op and group is not a string
        ValueError: If the first dimension of input can not be divided by rank size.

    Examples:
        >>> from mindspore.communication.management import init
        >>> init('nccl')
        >>> class Net(nn.Cell):
        >>>     def __init__(self):
        >>>         super(Net, self).__init__()
        >>>         self.reducescatter = ReduceScatter(ReduceOp.SUM, group="nccl_world_group")
        >>>
        >>>     def construct(self, x):
        >>>         return self.reducescatter(x)
        >>>
        >>> input_ = Tensor(np.ones([2, 8]).astype(np.float32))
        >>> net = Net()
        >>> output = net(input_)
    """

    @prim_attr_register
    def __init__(self, op=ReduceOp.SUM, group=GlobalComm.WORLD_COMM_GROUP):
        if not isinstance(op, type(ReduceOp.SUM)):
            raise TypeError("The operation of ReduceScatter should be {}.".format(type(ReduceOp.SUM)))
        if not isinstance(get_group(group), str):
            raise TypeError("The group of ReduceScatter should be str.")
        self.op = op
        self.rank_size = get_group_size(get_group(group))
        self.add_prim_attr('rank_size', self.rank_size)
        self.add_prim_attr('group', get_group(group))

    def infer_shape(self, x_shape):
        if x_shape[0] % self.rank_size != 0:
            raise ValueError("The first dimension of x should be divided by rank_size.")
        x_shape[0] = int(x_shape[0]/self.rank_size)
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype

    def __call__(self, tensor):
        raise NotImplementedError


class Broadcast(PrimitiveWithInfer):
    """
    Broadcasts the tensor to the whole group.

    Note:
        Tensor must have the same shape and format in all processes participating in the collective.

    Args:
        root_rank (int): Source rank. Required in all processes except the one
                   that is sending the data.
        group (str): The communication group to work on. Default: "hccl_world_group".

    Inputs:
        - **input_x** (Tensor) - The shape of tensor is :math:`(x_1, x_2, ..., x_R)`.

    Outputs:
        Tensor, has the same shape of the input, i.e., :math:`(x_1, x_2, ..., x_R)`.
        The contents depend on the data of the `root_rank` device.

    Raises:
        TypeError: If root_rank is not a integer or group is not a string.

    Examples:
        >>> from mindspore.communication.management import init
        >>> init('nccl')
        >>> class Net(nn.Cell):
        >>>     def __init__(self):
        >>>         super(Net, self).__init__()
        >>>         self.broadcast = Broadcast(1)
        >>>
        >>>     def construct(self, x):
        >>>         return self.broadcast((x,))
        >>>
        >>> input_ = Tensor(np.ones([2, 8]).astype(np.float32))
        >>> net = Net()
        >>> output = net(input_)
    """

    @prim_attr_register
    def __init__(self, root_rank, group=GlobalComm.WORLD_COMM_GROUP):
        if not isinstance(root_rank, int):
            raise TypeError("The root_rank of Broadcast should be int.")
        if not isinstance(get_group(group), str):
            raise TypeError("The group of Broadcast should be str.")
        self.add_prim_attr('group', get_group(group))

    def infer_shape(self, x_shape):
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype


class _AlltoAll(PrimitiveWithInfer):
    """
    AlltoAll is a collective operation.

    AlltoAll sends data from the all processes to the all processes in the specified group. It has two phases:

    - The scatter phase: On each process, the operand is split into split_count number of blocks along the
      split_dimensions, and the blocks are scattered to all processes, e.g., the ith block is send to the ith process.
    - The gather phase: Each process concatenates the received blocks along the concat_dimension.

    Note:
        Tensor must have the same shape and format in all processes participating in the collective.

    Args:
        split_count (int): On each process, divide blocks into split_count number.
        split_dim (int): On each process, split blocks along the split_dim.
        concat_dim (int): On each process, gather the received blocks along the concat_dimension.
        group (str): The communication group to work on. Default: "hccl_world_group".

    Raises:
        TypeError: If group is not a string.
    """

    @prim_attr_register
    def __init__(self, split_count, split_dim, concat_dim, group=GlobalComm.WORLD_COMM_GROUP):
        """init AlltoAll"""
        if not isinstance(get_group(group), str):
            raise TypeError("The group of AllGather should be str.")
        self.split_count = split_count
        self.split_dim = split_dim
        self.concat_dim = concat_dim
        self.add_prim_attr('group', get_group(group))

    def infer_shape(self, x_shape):
        x_shape[self.concat_dim] = x_shape[self.concat_dim] * self.split_count
        x_shape[self.split_dim] = int(x_shape[self.split_dim] / self.split_count)
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype

    def __call__(self, tensor):
        return


class _MirrorOperator(PrimitiveWithInfer):
    """
    Auto parallel virtual operator. Do nothing in forward, do all reduce and mean in backward. It is only for
    internal use of parallel modules and cannot be called by users.

    Args:
        group (str): The communication group to work on. Default: None.
        dev_num (int): The device number of the group. Default: None.
        mean_flag (bool): Whether use mean in backward. Default: None.
    """

    @prim_attr_register
    def __init__(self, group=None, dev_num=None, mean_flag=None):
        self.group = group
        self.dev_num = dev_num
        self.mean_flag = mean_flag

    def infer_shape(self, x_shape):
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype


mirror = _MirrorOperator()


class _VirtualDiv(PrimitiveWithInfer):
    """
    Auto parallel virtual operator. Do nothing in forward, do Div in backward.

    Args:
        divisor: float32
    """
    @prim_attr_register
    def __init__(self, divisor=None):
        self.divisor = divisor

    def infer_shape(self, x_shape):
        return x_shape

    def infer_dtype(self, x_dtype):
        return x_dtype


virtual_div = _VirtualDiv()


class _VirtualDataset(PrimitiveWithInfer):
    """
    Auto parallel virtual dataset operator.

    It would insert Broadcast operator in forward computation and be deleted before backward computation.
    """

    @prim_attr_register
    def __init__(self):
        """init"""

    def infer_shape(self, *args):
        if len(args) == 1:
            return args[0]
        return args

    def infer_dtype(self, *args):
        if len(args) == 1:
            return args[0]
        return args


virtual_dataset = _VirtualDataset()


class _GetTensorSlice(PrimitiveWithInfer):
    """
    Gets tensor slice by device matrix and tensor map.

    Args:
        dev_mat (tuple): The device matrix of the slice tensor.
        tensor_map (tuple): The tensor map of the slice tensor.
    """

    @prim_attr_register
    def __init__(self):
        """init ChunkTensor"""

    def infer_value(self, x, dev_mat, tensor_map):
        from mindspore.parallel._tensor import _load_tensor
        validator.check_type("dev_mat", dev_mat, [tuple])
        validator.check_type("tensor_map", tensor_map, [tuple])
        return _load_tensor(x, dev_mat, tensor_map)
