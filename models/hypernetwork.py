# copy from https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/c344ba3b325459abbf9b0df2c1b18f7bf99805b2/modules/hypernetworks/hypernetwork.py

import os
import torch
from torch.nn.init import normal_

class HypernetworkModule(torch.nn.Module):
    multiplier = 1.0

    def __init__(self, dim, state_dict=None):
        super().__init__()

        linears = []
#         linears.append(torch.nn.Linear(dim, dim * 2))
#         linears.append(torch.nn.Linear(dim * 2, dim))
        # linears.append(torch.nn.ReLU())
        linears.append(torch.nn.Linear(dim, dim * 4))
        linears.append(torch.nn.LeakyReLU())
        linears.append(torch.nn.Linear(dim * 4, dim * 4))
        linears.append(torch.nn.LeakyReLU())
        linears.append(torch.nn.Linear(dim * 4, dim))
        self.linear = torch.nn.Sequential(*linears)

        if state_dict is not None:
            self.load_state_dict(state_dict, strict=True)
        else:
            for layer in self.linear:
                if type(layer) == torch.nn.Linear or type(layer) == torch.nn.LayerNorm:
                    w, b = layer.weight.data, layer.bias.data
                    normal_(w, mean=0.0, std=0.01)
                    normal_(b, mean=0.0, std=0)

    def forward(self, x):
        return x + self.linear(x) * self.multiplier

    def trainables(self):
        layer_structure = []
        for layer in self.linear:
            if type(layer) == torch.nn.Linear or type(layer) == torch.nn.LayerNorm:
                layer_structure += [layer.weight, layer.bias]
        return layer_structure


class Hypernetwork:
    filename = None
    name = None

    def __init__(self, name=None, enable_sizes=None):
        self.filename = None
        self.name = name
        self.layers = {}
        self.step = 0
        self.sd_checkpoint = None
        self.sd_checkpoint_name = None

        for key, size in enable_sizes or []:
            self.layers[f"{key}_{size}"] = (HypernetworkModule(size), HypernetworkModule(size))

    def to(self, device):
        for k, layers in self.layers.items():
            for layer in layers:
                layer.to(device)

    def train(self):
        for k, layers in self.layers.items():
            for layer in layers:
                layer.train()

    def weights(self):
        res = []

        for k, layers in self.layers.items():
            for layer in layers:
                layer.train()
                res += layer.trainables()

        return res

    def save(self, filename):
        state_dict = {}

        for k, v in self.layers.items():
            state_dict[k] = (v[0].state_dict(), v[1].state_dict())

        state_dict['step'] = self.step
        state_dict['name'] = self.name
        state_dict['sd_checkpoint'] = self.sd_checkpoint
        state_dict['sd_checkpoint_name'] = self.sd_checkpoint_name

        torch.save(state_dict, filename)

    def load(self, filename):
        self.filename = filename
        if self.name is None:
            self.name = os.path.splitext(os.path.basename(filename))[0]

        state_dict = torch.load(filename, map_location='cpu')

        for size, sd in state_dict.items():
            if type(size) == int:
                self.layers[size] = (HypernetworkModule(size, sd[0]), HypernetworkModule(size, sd[1]))

        self.name = state_dict.get('name', self.name)
        self.step = state_dict.get('step', 0)
        self.sd_checkpoint = state_dict.get('sd_checkpoint', None)
        self.sd_checkpoint_name = state_dict.get('sd_checkpoint_name', None)
