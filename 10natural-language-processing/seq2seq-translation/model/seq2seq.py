import torch
import torch.nn.functional as F
from torch import nn
from torch.autograd import Variable

MAX_LENGTH = 10
use_cuda = torch.cuda.is_available()


class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size, n_layers=1):
        super(EncoderRNN, self).__init__()
        self.n_layers = n_layers
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(input_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size)

    def forward(self, x, hidden):
        """
        :param x: batch(1)
        :param hidden:
        :return:
        """
        x = x.unsqueeze(1)  # batch(1), 1
        embedded = self.embedding(x)  # batch(1), 1, hidden
        output = embedded.permute(1, 0, 2)  # 1, batch, hidden
        for i in range(self.n_layers):
            # 1(seq_len), batch, hidden  1(num_layers*num_directions), batch, hidden
            output, hidden = self.gru(output, hidden)
        return output, hidden

    def init_hidden(self):
        result = Variable(torch.zeros(1, 1, self.hidden_size))
        if use_cuda:
            return result.cuda()
        else:
            return result


class DecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, n_layers=1):
        super(DecoderRNN, self).__init__()
        self.n_layers = n_layers
        self.hidden_size = hidden_size

        self.embedding = nn.Embedding(output_size, hidden_size)
        self.gru = nn.GRU(hidden_size, hidden_size)
        self.out = nn.Linear(hidden_size, output_size)
        self.softmax = nn.LogSoftmax(dim=-1)

    def forward(self, x, hidden):
        """
        :param x: 1(batch),1(word)
        :param hidden: 1, 1, 256
        :return:
        """
        output = self.embedding(x)  # batch, 1, hidden
        output = output.permute(1, 0, 2)  # 1, batch, hidden
        for i in range(self.n_layers):
            output = F.relu(output)
            # 1(seq_len), 1(batch),hidden  1, 1, hidden
            output, hidden = self.gru(output, hidden)
        output = self.softmax(self.out(output[0]))  # 1(batch), output_size
        return output, hidden

    def init_hidden(self):
        result = Variable(torch.zeros((1, 1, self.hidden_size)))
        if use_cuda:
            return result.cuda()
        else:
            return result


class AttnDecoderRNN(nn.Module):
    def __init__(self,
                 hidden_size,
                 output_size,
                 n_layers=1,
                 dropout_p=0.1,
                 max_length=MAX_LENGTH):
        super(AttnDecoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.n_layers = n_layers
        self.dropout_p = dropout_p
        self.max_length = max_length

        self.embedding = nn.Embedding(self.output_size, self.hidden_size)
        self.attn = nn.Linear(self.hidden_size * 2, self.max_length)
        self.attn_combine = nn.Linear(self.hidden_size * 2, self.hidden_size)
        self.dropout = nn.Dropout(self.dropout_p)
        self.gru = nn.GRU(self.hidden_size, self.hidden_size)
        self.out = nn.Linear(self.hidden_size, self.output_size)

    def forward(self, x, hidden, encoder_outputs):
        """
        :param x: batch, 1
        :param hidden: 1, 1(batch), hidden
        :param encoder_outputs: max_length, hidden
        :return:
        """
        embedded = self.embedding(x)  # batch, 1, hidden
        embedded = self.dropout(embedded)
        embedded = embedded.squeeze(1)  # batch, hidden
        # batch, max_length
        attn_weights = F.softmax(
            self.attn(torch.cat((embedded, hidden[0]), 1)), dim=-1)

        encoder_outputs = encoder_outputs.unsqueeze(0)  # 1, max_length, hidden
        attn_applied = torch.bmm(attn_weights.unsqueeze(1), encoder_outputs)  # batch, 1, hidden
        output = torch.cat((embedded, attn_applied.squeeze(1)), 1)  # batch, 2 x hidden
        output = self.attn_combine(output).unsqueeze(0)  # 1, batch, hidden

        for i in range(self.n_layers):
            output = F.relu(output)
            output, hidden = self.gru(output, hidden)
        # 1, batch, hidden    1, batch, hidden
        output = F.log_softmax(self.out(output.squeeze(0)), dim=-1)  # batch, output_size
        return output, hidden, attn_weights

    def init_hidden(self):
        result = Variable(torch.zeros(1, 1, self.hidden_size))
        if use_cuda:
            return result.cuda()
        else:
            return result
