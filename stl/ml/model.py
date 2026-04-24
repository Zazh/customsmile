"""
MeshSegNet — exact architecture from Tai-Hsien et al.
https://github.com/Tai-Hsien/MeshSegNet

Input:
  x   — (B, 15, N) per-face features
  a_s — (B, N, N) small-radius adjacency matrix
  a_l — (B, N, N) large-radius adjacency matrix

Output:
  (B, N, num_classes) per-face softmax probabilities
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class STNkd(nn.Module):
    """Feature Transformer Module (FTM)."""

    def __init__(self, k=64):
        super().__init__()
        self.k = k
        self.conv1 = nn.Conv1d(k, 64, 1)
        self.conv2 = nn.Conv1d(64, 128, 1)
        self.conv3 = nn.Conv1d(128, 512, 1)
        self.fc1 = nn.Linear(512, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, k * k)
        self.bn1 = nn.BatchNorm1d(64)
        self.bn2 = nn.BatchNorm1d(128)
        self.bn3 = nn.BatchNorm1d(512)
        self.bn4 = nn.BatchNorm1d(256)
        self.bn5 = nn.BatchNorm1d(128)

    def forward(self, x):
        B = x.size(0)
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = torch.max(x, 2, keepdim=True)[0].view(-1, 512)
        x = F.relu(self.bn4(self.fc1(x)))
        x = F.relu(self.bn5(self.fc2(x)))
        x = self.fc3(x)

        iden = torch.eye(self.k, dtype=x.dtype, device=x.device).flatten().unsqueeze(0).repeat(B, 1)
        x = x + iden
        return x.view(-1, self.k, self.k)


class MeshSegNet(nn.Module):
    def __init__(self, num_classes=15, num_channels=15, with_dropout=True, dropout_p=0.5):
        super().__init__()
        self.num_classes = num_classes
        self.num_channels = num_channels
        self.with_dropout = with_dropout

        # MLP-1 [64, 64]
        self.mlp1_conv1 = nn.Conv1d(num_channels, 64, 1)
        self.mlp1_conv2 = nn.Conv1d(64, 64, 1)
        self.mlp1_bn1 = nn.BatchNorm1d(64)
        self.mlp1_bn2 = nn.BatchNorm1d(64)

        # FTM
        self.fstn = STNkd(k=64)

        # GLM-1 (Graph-constrained Learning Module)
        self.glm1_conv1_1 = nn.Conv1d(64, 32, 1)
        self.glm1_conv1_2 = nn.Conv1d(64, 32, 1)
        self.glm1_bn1_1 = nn.BatchNorm1d(32)
        self.glm1_bn1_2 = nn.BatchNorm1d(32)
        self.glm1_conv2 = nn.Conv1d(64, 64, 1)
        self.glm1_bn2 = nn.BatchNorm1d(64)

        # MLP-2
        self.mlp2_conv1 = nn.Conv1d(64, 64, 1)
        self.mlp2_bn1 = nn.BatchNorm1d(64)
        self.mlp2_conv2 = nn.Conv1d(64, 128, 1)
        self.mlp2_bn2 = nn.BatchNorm1d(128)
        self.mlp2_conv3 = nn.Conv1d(128, 512, 1)
        self.mlp2_bn3 = nn.BatchNorm1d(512)

        # GLM-2
        self.glm2_conv1_1 = nn.Conv1d(512, 128, 1)
        self.glm2_conv1_2 = nn.Conv1d(512, 128, 1)
        self.glm2_conv1_3 = nn.Conv1d(512, 128, 1)
        self.glm2_bn1_1 = nn.BatchNorm1d(128)
        self.glm2_bn1_2 = nn.BatchNorm1d(128)
        self.glm2_bn1_3 = nn.BatchNorm1d(128)
        self.glm2_conv2 = nn.Conv1d(384, 512, 1)
        self.glm2_bn2 = nn.BatchNorm1d(512)

        # MLP-3 (dense fusion: 64 + 512 + 512 + 512 = 1600)
        self.mlp3_conv1 = nn.Conv1d(1600, 256, 1)
        self.mlp3_conv2 = nn.Conv1d(256, 256, 1)
        self.mlp3_bn1_1 = nn.BatchNorm1d(256)
        self.mlp3_bn1_2 = nn.BatchNorm1d(256)
        self.mlp3_conv3 = nn.Conv1d(256, 128, 1)
        self.mlp3_conv4 = nn.Conv1d(128, 128, 1)
        self.mlp3_bn2_1 = nn.BatchNorm1d(128)
        self.mlp3_bn2_2 = nn.BatchNorm1d(128)

        # Output
        self.output_conv = nn.Conv1d(128, num_classes, 1)
        if with_dropout:
            self.dropout = nn.Dropout(p=dropout_p)

    def forward(self, x, a_s, a_l):
        """
        Args:
            x:   (B, 15, N) per-face features
            a_s: (B, N, N) small-radius adjacency (row-normalized)
            a_l: (B, N, N) large-radius adjacency (row-normalized)
        Returns:
            (B, N, num_classes) softmax probabilities
        """
        B = x.size(0)
        N = x.size(2)

        # MLP-1
        x = F.relu(self.mlp1_bn1(self.mlp1_conv1(x)))
        x = F.relu(self.mlp1_bn2(self.mlp1_conv2(x)))

        # FTM
        trans_feat = self.fstn(x)
        x = x.transpose(2, 1)
        x_ftm = torch.bmm(x, trans_feat)

        # GLM-1
        sap = torch.bmm(a_s, x_ftm)
        sap = sap.transpose(2, 1)
        x_ftm_t = x_ftm.transpose(2, 1)
        x = F.relu(self.glm1_bn1_1(self.glm1_conv1_1(x_ftm_t)))
        glm_1_sap = F.relu(self.glm1_bn1_2(self.glm1_conv1_2(sap)))
        x = torch.cat([x, glm_1_sap], dim=1)
        x = F.relu(self.glm1_bn2(self.glm1_conv2(x)))

        # MLP-2
        x = F.relu(self.mlp2_bn1(self.mlp2_conv1(x)))
        x = F.relu(self.mlp2_bn2(self.mlp2_conv2(x)))
        x_mlp2 = F.relu(self.mlp2_bn3(self.mlp2_conv3(x)))
        if self.with_dropout:
            x_mlp2 = self.dropout(x_mlp2)

        # GLM-2
        x_mlp2_t = x_mlp2.transpose(2, 1)
        sap_1 = torch.bmm(a_s, x_mlp2_t).transpose(2, 1)
        sap_2 = torch.bmm(a_l, x_mlp2_t).transpose(2, 1)
        x = F.relu(self.glm2_bn1_1(self.glm2_conv1_1(x_mlp2)))
        glm_2_sap_1 = F.relu(self.glm2_bn1_2(self.glm2_conv1_2(sap_1)))
        glm_2_sap_2 = F.relu(self.glm2_bn1_3(self.glm2_conv1_3(sap_2)))
        x = torch.cat([x, glm_2_sap_1, glm_2_sap_2], dim=1)
        x_glm2 = F.relu(self.glm2_bn2(self.glm2_conv2(x)))

        # Global Max Pooling + Upsample
        x = torch.max(x_glm2, 2, keepdim=True)[0]
        x = torch.nn.Upsample(N)(x)

        # Dense fusion
        x = torch.cat([x, x_ftm_t, x_mlp2, x_glm2], dim=1)

        # MLP-3
        x = F.relu(self.mlp3_bn1_1(self.mlp3_conv1(x)))
        x = F.relu(self.mlp3_bn1_2(self.mlp3_conv2(x)))
        x = F.relu(self.mlp3_bn2_1(self.mlp3_conv3(x)))
        if self.with_dropout:
            x = self.dropout(x)
        x = F.relu(self.mlp3_bn2_2(self.mlp3_conv4(x)))

        # Output
        x = self.output_conv(x)
        x = x.transpose(2, 1).contiguous()
        x = torch.softmax(x.view(-1, self.num_classes), dim=-1)
        x = x.view(B, N, self.num_classes)

        return x
