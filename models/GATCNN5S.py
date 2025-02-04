# -*- coding: utf-8 -*-
import torch.nn
import scipy.sparse as sp
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from models.gatbackbone import SliceEmbeddingImagenet
from models.layers import GraphAttentionLayer

# from gatbackbone import SliceEmbeddingImagenet
# from layers import GraphAttentionLayer

# from layers1 import GraphAttentionLayer, UG_GraphAttentionLayer
def normalize(mx):
    """Row-normalize sparse matrix"""
    rowsum = np.array(mx.sum(1))
    r_inv = np.power(rowsum, -1).flatten()
    r_inv[np.isinf(r_inv)] = 0.
    r_mat_inv = sp.diags(r_inv)
    mx = r_mat_inv.dot(mx)
    return mx

class GATEmbedding(nn.Module):

    def __init__(self, mid_nodes, emb_size, nfeat, nhid, nclass, dropout, alpha, nheads):
        super(GATEmbedding, self).__init__()
        self.mid_nodes = mid_nodes
        self.emb_size = emb_size
        self.dropout = dropout

        self.slice_featuer = SliceEmbeddingImagenet(self.emb_size)

        # LIDP
        # self.struct_embedding = nn.ModuleList([torch.nn.Embedding(5, self.emb_size),
        #                                        torch.nn.Embedding(2, self.emb_size),
        #                                        torch.nn.Embedding(2, self.emb_size),
        #                                        torch.nn.Embedding(2, self.emb_size),
        #                                        torch.nn.Embedding(50, self.emb_size),
        #                                        torch.nn.Embedding(3, self.emb_size),
        #                                        torch.nn.Embedding(2, self.emb_size),
        #                                        # torch.nn.Embedding(2, self.emb_size),
        #                                        # torch.nn.Embedding(100, self.emb_size)
        #                                        ])
        # LIDC
        self.struct_embedding = nn.ModuleList([torch.nn.Embedding(4, self.emb_size),
                                               torch.nn.Embedding(5, self.emb_size),
                                               torch.nn.Embedding(5, self.emb_size),
                                               torch.nn.Embedding(5, self.emb_size),
                                               torch.nn.Embedding(5, self.emb_size),
                                               torch.nn.Embedding(3, self.emb_size),
                                               torch.nn.Embedding(4, self.emb_size),
                                               torch.nn.Embedding(4, self.emb_size),
                                               torch.nn.Embedding(50, self.emb_size),
                                               ])

        self.attentions = [GraphAttentionLayer(nfeat, nhid, dropout=dropout, alpha=alpha, concat=True) for _ in range(nheads)]
        for i, attention in enumerate(self.attentions):
            self.add_module('attention_{}'.format(i), attention)
        self.out_att1 = GraphAttentionLayer(nhid * nheads, self.emb_size, dropout=dropout, alpha=alpha, concat=False)
        
        self.layer_last = nn.Sequential(nn.Linear(in_features=self.emb_size,out_features=self.emb_size*2),
                                        nn.ReLU(True),
                                        nn.Dropout(0.3),
                                        )
        self.fc = nn.Linear(self.emb_size*2, 2)
        self.slice_fc = nn.Linear(emb_size, 2)

    def forward(self, input_img, input_struct=None):
        batch_size, c, h, w = input_img.size()
        img_slices = torch.zeros([batch_size, c+self.mid_nodes, self.emb_size], device=input_img.device)
        slices_features = [self.slice_featuer(value)[0] for value in input_img.chunk(input_img.size(1), dim=1)]
        slices_features_stack = torch.stack(slices_features, dim=1)

        # for slice loss
        slices_hidden = slices_features_stack.mean(dim=1)
        slices_out = self.slice_fc(slices_hidden)

        img_slices[:, self.mid_nodes:, :] = slices_features_stack

        output_struct = []
        for index, value in enumerate(input_struct.chunk(input_struct.size(1), dim=1)):
            value = value.view(-1).long()
            oo = self.struct_embedding[index](value)
            output_struct.append(oo)
        struct_feas = torch.stack(output_struct, dim=1).to(input_img.device)  # batch_size X 9 X emb_size 新增一个维度且要求形状相同

        # struct_feas = self.struct_embedding(input_struct).unsqueeze(1)

        slices = torch.cat([img_slices, struct_feas], dim=1)

        adj = self.get_adj(slices.size(1), struct_feas.size(1)).to(input_img.device)  # N X N

        adj = adj.unsqueeze(0).repeat(slices.size(0), 1, 1)  # B X N X N

        x = F.dropout(slices, self.dropout, training=self.training)

        # 2
        batch_attention = torch.stack([att(x, adj)[1] for att in self.attentions], dim=1).mean(dim=1)  # B X 3 X  N X N
        x = torch.cat([att(x, adj)[0] for att in self.attentions], dim=-1)  # B X N X nhid * nheads

        x = F.dropout(x, self.dropout, training=self.training)
        image_feature = F.elu(self.out_att1(x, adj)[0])  # B X N X emb_size
        # 1
        # batch_attention = self.out_att1(x, adj)[1]  # B X N X N
        image_feature = F.dropout(image_feature, self.dropout, training=self.training)

        image_feature_second = image_feature[:, 0, :].squeeze(1)  # B X emb_size

        feature = self.layer_last(image_feature_second)

        return slices_hidden, feature, self.fc(feature), slices_out, batch_attention

    def get_adj(self, all_num, strcut_num):
        N = all_num - strcut_num
        if self.mid_nodes > 0:
            mid = ((N - self.mid_nodes) // 2 + self.mid_nodes) - 1
            width = ((N - self.mid_nodes) // self.mid_nodes) // 2
            width_list = [width * (i + 1) for i in range(self.mid_nodes)]
        adjMetrix = []

        for i in range(self.mid_nodes):
            adjMetrix.append([])
            for j in range(all_num):
                if i == (self.mid_nodes - 1):
                    if j > (self.mid_nodes - 1):
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)
                else:
                    if j == (i + 1) or (j > mid - width_list[i] and j < mid + width_list[i]) or j >= N:
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)

        for i in range(self.mid_nodes, all_num):
            adjMetrix.append([])
            for j in range(all_num):
                if i == self.mid_nodes:
                    if j == (self.mid_nodes + 1):
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)
                elif i == N - 1:
                    if j == N - 2:
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)
                elif i >= N:
                    if j >= N:
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)
                else:
                    if j == i - 1 or j == i + 1:
                        adjMetrix[i].append(1)
                    else:
                        adjMetrix[i].append(0)

        adjMetrix = sp.coo_matrix(adjMetrix)
        adjMetrix = normalize(adjMetrix + sp.eye(adjMetrix.shape[0]))
        adjMetrix = adjMetrix.todense()
        adjMetrix = torch.from_numpy(adjMetrix)
        adjMetrix = adjMetrix.float()
        return adjMetrix


from torchsummary import summary
#
# from config.data_config import config
# cf = config()

# model = GATEmbedding(mid_nodes, emb_size, nfeat, nhid, nclass, dropout, alpha, nheads)

model = GATEmbedding(mid_nodes=7,
                      emb_size=64,
                      nfeat=64,
                      nhid=64,
                      nclass=2,
                      dropout=0.2,
                      nheads=4,
                      alpha=0.2)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

input_img_shape = (32, 32, 32)  
input_struct_shape = (9,)       

summary(model, [input_img_shape, input_struct_shape])
