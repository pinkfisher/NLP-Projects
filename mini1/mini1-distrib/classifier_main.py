# classifier_main.py

import argparse
import sys
import time
from nerdata import *
from utils import *
from collections import Counter
from optimizers import *
from typing import List
import scipy.sparse
import string
import pickle
import nltk

def _parse_args():
    """
    Command-line arguments to the system. --model switches between the main modes you'll need to use. The other arguments
    are provided for convenience.
    :return: the parsed args bundle
    """
    parser = argparse.ArgumentParser(description='trainer.py')
    parser.add_argument('--model', type=str, default='BAD', help='model to run (BAD, CLASSIFIER)')
    parser.add_argument('--train_path', type=str, default='data/eng.train', help='path to train set (you should not need to modify)')
    parser.add_argument('--dev_path', type=str, default='data/eng.testa', help='path to dev set (you should not need to modify)')
    parser.add_argument('--blind_test_path', type=str, default='data/eng.testb.blind', help='path to dev set (you should not need to modify)')
    parser.add_argument('--test_output_path', type=str, default='eng.testb.out', help='output path for test predictions')
    parser.add_argument('--no_run_on_test', dest='run_on_test', default=True, action='store_false', help='skip printing output on the test set')
    args = parser.parse_args()
    return args


class PersonExample(object):
    """
    Data wrapper for a single sentence for person classification, which consists of many individual tokens to classify.

    Attributes:
        tokens: the sentence to classify
        labels: 0 if non-person name, 1 if person name for each token in the sentence
    """

    def __init__(self, tokens: List[str], labels: List[int]):
        self.tokens = tokens
        self.labels = labels

    def __len__(self):
        return len(self.tokens)


def transform_for_classification(ner_exs: List[LabeledSentence]):
    """
    :param ner_exs: List of chunk-style NER examples
    :return: A list of PersonExamples extracted from the NER data
    """
    for labeled_sent in ner_exs:
        tags = bio_tags_from_chunks(labeled_sent.chunks, len(labeled_sent))
        labels = [1 if tag.endswith("PER") else 0 for tag in tags]
        yield PersonExample([tok.word for tok in labeled_sent.tokens], labels)



class CountBasedPersonClassifier(object):
    """
    Person classifier that takes counts of how often a word was observed to be the positive and negative class
    in training, and classifies as positive any tokens which are observed to be positive more than negative.
    Unknown tokens or ties default to negative.
    Attributes:
        pos_counts: how often each token occurred with the label 1 in training
        neg_counts: how often each token occurred with the label 0 in training
    """
    def __init__(self, pos_counts: Counter, neg_counts: Counter):
        self.pos_counts = pos_counts
        self.neg_counts = neg_counts

    def predict(self, tokens: List[str], idx: int):
        if self.pos_counts[tokens[idx]] > self.neg_counts[tokens[idx]]:
            return 1
        else:
            return 0


def train_count_based_binary_classifier(ner_exs: List[PersonExample]):
    """
    :param ner_exs: training examples to build the count-based classifier from
    :return: A CountBasedPersonClassifier using counts collected from the given examples
    """
    pos_counts = Counter()
    neg_counts = Counter()
    for ex in ner_exs:
        for idx in range(0, len(ex)):
            if ex.labels[idx] == 1:
                pos_counts[ex.tokens[idx]] += 1.0
            else:
                neg_counts[ex.tokens[idx]] += 1.0
    print(repr(pos_counts))
    print(repr(pos_counts["Peter"]))
    print(repr(pos_counts["aslkdjtalk;sdjtakl"]))
    return CountBasedPersonClassifier(pos_counts, neg_counts)


class PersonClassifier(object):
    """
    Classifier to classify a token in a sentence as a PERSON token or not.
    Constructor arguments are merely suggestions; you're free to change these.
    """

    def __init__(self, weights: np.ndarray, indexer: Indexer):
        self.weights = weights
        self.indexer = indexer

    def predict(self, tokens: List[str], idx: int):
        """
        Makes a prediction for token at position idx in the given PersonExample
        :param tokens:
        :param idx:
        :return: 0 if not a person token, 1 if a person token
        """

    def predict(self, tokens, idx):
        # feat = get_feature_vector(self.indexer, tokens, pos_tags, idx, False)
        feat = get_feature_vector(self.indexer, tokens, idx, False)

        ## TODO: Debugging code in the predict function
        # for f in feat:
        #     print("Feature of interests for this example: ", self.indexer.ints_to_objs[f])
        #     print("Weight for above feature: ", self.weights[f])

        logistics_score = logistic(feat, self.weights)
        ## TODO: Printing scores for debugging
        # print("Model score: ", score_indexed_features(feat, self.weights))
        # print("Logistics score: ", logistics_score)
        if logistics_score >= 0.5:
            return 1
        else:
            return 0
        # raise Exception("Implement me!")

def logistic(instance, weights):
    score = score_indexed_features(instance, weights)
    # exp_calc = np.exp(sum(np.multiply(weights, instance)))
    exp_calc = np.exp(score)
    return exp_calc/(1+exp_calc)


def compute_gradient(logistics_score, instance, label):
    # sparse_gradient = instance * (label - logistics_score)
    # indices = np.nonzero(sparse_gradient)[0]
    gradient = Counter()
    for i in instance:
        gradient[i] = 1 * (label - logistics_score)
    return gradient


def get_feature_vector(indexer, tokens, idx, add=True):
    # Sparse feature vectors stores the feature as the index to be marked as 1
    # currentFeature = [prevWordIndex, currWordIndex, nextWordIndex]
    currentFeature = []

    if (idx - 1) >= 0:
        featurePrevWord = "PrevWord=" + tokens[(idx - 1)]
        maybe_add_feature(currentFeature, indexer, add, featurePrevWord)
    else:
        featurePrevWord = "PrevWord=" + "BOS"
        maybe_add_feature(currentFeature, indexer, add, featurePrevWord)

    featureCurrWord = "CurrWord=" + tokens[idx]
    maybe_add_feature(currentFeature, indexer, add, featureCurrWord)

    try:
        featureNextWord = "NextWord=" + tokens[idx + 1]
        maybe_add_feature(currentFeature, indexer, add, featureNextWord)
    except:
        featureNextWord = "NextWord=" + "EOS"
        maybe_add_feature(currentFeature, indexer, add, featureNextWord)

    # Last word in the dev is always a ".". So EOS should be the word before that
    try:
        if(tokens[idx+1] == '.'):
            featureLastWord = "LastWord"
            maybe_add_feature(currentFeature, indexer, add, featureLastWord)
    except:
        pass

    if (idx - 2) >= 0:
        featureSecondLastWord = "prev-1Word=" + tokens[(idx-2)]
        maybe_add_feature(currentFeature, indexer, add, featureSecondLastWord)

    ## TODO: Experimenting with commenting out isfirstLetterCap : Improved accuracy
    # If the first letter of the word is capitalized
    # if(tokens[idx][0].isupper()):
    #     maybe_add_feature(currentFeature, indexer, add, "isFirstLetterCap")

    # If the first word is cap but second letter of the word not capitalized
    if len(tokens[idx]) > 1 and tokens[idx][0].isupper() and tokens[idx][1].islower():
        maybe_add_feature(currentFeature, indexer, add, "isFirstCapSecondNotCap")

    # # Next word is capitalized
    try:
        if tokens[idx + 1][0].isupper():
            maybe_add_feature(currentFeature, indexer, add, "NextWordCap")
    #     #     if tokens[idx+1][0] in string.punctuation:
    #     #         maybe_add_feature(currentFeature, indexer, add, "NextWordPunctuation")
    except:
        pass

    ## Position of the word in a sentence
    # max_sen_leng = 32
    # if (len(tokens) < 32):
    #     maybe_add_feature(currentFeature, indexer, add, "SentencePosition" + str(idx))

    ## Bias feature
    maybe_add_feature(currentFeature, indexer, add, "Bias")

    ## TODO: Commenting out second word as it tends to push down accuracy
    # try:
    #     featureSecondWord = "secondWord=" + tokens[(idx+2)]
    #     maybe_add_feature(currentFeature, indexer, add, featureSecondWord)
    # except:
    #     pass

    # if (idx - 3) >= 0:
    #     featureThirdLastWord = "thirdLastWord=" + tokens[(idx-3)]
    #     maybe_add_feature(currentFeature, indexer, add, featureThirdLastWord)
    #
    ## TODO: Commenting out third word as it tends to push down accuracy
    # try:
    #     featureThirdWord = "thirdWord=" + tokens[(idx+3)]
    #     maybe_add_feature(currentFeature, indexer, add, featureThirdWord)
    # except:
    #     pass

    ## TODO: Commenting out fourth word as it tends to push down accuracy
    # try:
    #     featureFourthWord = "fourthWord=" + tokens[(idx+4)]
    #     maybe_add_feature(currentFeature, indexer, add, featureFourthWord)
    # except:
    #     pass

    ## Additional features
    # TODO: Features: Noun?, positionOfCurrWordInSentence: Numeric??
    ## TODO: If the word in context is a noun
    ## TODO: Used POS tags to get this feautre
    # If the word is a noun
    # if pos_tags[idx] == 'NNP':
    #     maybe_add_feature(currentFeature, indexer, add, "isProperNoun")

    ## TODO: Experiment and fix the punctuation feature

    # if idx-1 >= 0:
    #     TODO: NOTE: PrevWord cap seems to add a lot of negative weight and contributes to wrong classification
    #     if tokens[idx-1][0].isupper():
    #         maybe_add_feature(currentFeature, indexer, add, "PrevWordCap")
    #     # Previous word is a punctuation mark
    #     if tokens[idx-1] in string.punctuation:
    #         maybe_add_feature(currentFeature, indexer, add, "prevWordPunc")
    # # if len(tokens[idx]) >= 4:
    # #     maybe_add_feature(currentFeature, indexer, add, "isCurrWordLong")
    #

    return currentFeature

def train_classifier(ner_exs: List[PersonExample]):
    featureIndex = Indexer()
    training_set = []
    labels = []
    len_exp = len(ner_exs)
    # print("total examples", len_exp)
    len_sen_list =[]
    # Build Index from vocabulary
    for ex in ner_exs:
        len_sen_list.append(len(ex))
        for idx in range(0, len(ex)):
            currentFeature = get_feature_vector(featureIndex, ex.tokens, idx)
            training_set.append(currentFeature)
            labels.append(ex.labels[idx])
    featureLength = len(featureIndex.ints_to_objs)
    print("Total number of features:", featureLength)

    # Model Hyper-parameters
    batch_size = 1
    ## TODO: Change epoch size to 25
    training_epochs = 25

    # TODO: Finalize on the optimizer to be used
    # Initialize the optimizer
    # optimizer = SGDOptimizer(np.zeros(featureLength), alpha = 1)
    # optimizer = UnregularizedAdagradTrainer(np.zeros(featureLength), eta=1.0)
    ## TODO: Change the eta and lambda value to the highest so far? lamb -10, eta 5.0
    optimizer = L1RegularizedAdagradTrainer(np.zeros(featureLength), lamb=1e-10, eta=5.0, use_regularization=True)

    # Loop over epochs
    for epoch in range(0, training_epochs):
        epoch_start_time = time.time()
        print("Training epoch: ", epoch)
        print("=========================")
        for training_idx in range(0, len(training_set)):
            training_instance = training_set[training_idx]
            logistics_score = logistic(training_instance, optimizer.weights)
            gradient_update = compute_gradient(logistics_score, training_instance, labels[training_idx])
            # Gradient Update
            optimizer.apply_gradient_update(gradient_update, batch_size)
            # if training_idx % 1000 == 0:
                # print("training done for {0} of {1} items".format(training_idx, len(training_set)))
                # print("objective: ", logistics_score)
        print("For epoch ", epoch, "Training took %f seconds" % (time.time() - epoch_start_time))
        # evaluate_classifier(ner_exs, PersonClassifier(optimizer.get_final_weights(), featureIndex))
    return(PersonClassifier(optimizer.get_final_weights(), featureIndex))

def evaluate_classifier(exs: List[PersonExample], classifier: PersonClassifier):
    """
    Prints evaluation of the classifier on the given examples
    :param exs: PersonExample instances to run on
    :param classifier: classifier to evaluate
    """
    predictions = []
    golds = []
    for ex in exs:
        for idx in range(0, len(ex)):
            golds.append(ex.labels[idx])
            pred_label = classifier.predict(ex.tokens, idx)
            predictions.append(pred_label)
            ## TODO: Debugging: Comment out prints in evaluate classifier
            # print("========================New Example==========================")
            # if ex.labels[idx] != pred_label:
            #     print("example:", ex.tokens)
            #     print("token of interest", ex.tokens[idx])
            #     print("Gold Label for above: ", ex.labels[idx])
            #     print("Predicted label for above: ", pred_label)
            #     print("===============================================================")
    print_evaluation(golds, predictions)


def print_evaluation(golds: List[int], predictions: List[int]):
    """
    Prints statistics about accuracy, precision, recall, and F1
    :param golds: list of {0, 1}-valued ground-truth labels for each token in the test set
    :param predictions: list of {0, 1}-valued predictions for each token
    :return:
    """
    num_correct = 0
    num_pos_correct = 0
    num_pred = 0
    num_gold = 0
    num_total = 0
    if len(golds) != len(predictions):
        raise Exception("Mismatched gold/pred lengths: %i / %i" % (len(golds), len(predictions)))
    for idx in range(0, len(golds)):
        gold = golds[idx]
        prediction = predictions[idx]
        if prediction == gold:
            num_correct += 1
        if prediction == 1:
            num_pred += 1
        if gold == 1:
            num_gold += 1
        if prediction == 1 and gold == 1:
            num_pos_correct += 1
        num_total += 1
    print("Accuracy: %i / %i = %f" % (num_correct, num_total, float(num_correct) / num_total))
    prec = float(num_pos_correct) / num_pred if num_pred > 0 else 0.0
    rec = float(num_pos_correct) / num_gold if num_gold > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec > 0 and rec > 0 else 0.0
    print("Precision: %i / %i = %f" % (num_pos_correct, num_pred, prec))
    print("Recall: %i / %i = %f" % (num_pos_correct, num_gold, rec))
    print("F1: %f" % f1)


def predict_write_output_to_file(exs: List[PersonExample], classifier: PersonClassifier, outfile: str):
    """
    Runs prediction on exs and writes the outputs to outfile, one token per line
    :param exs:
    :param classifier:
    :param outfile:
    :return:
    """
    f = open(outfile, 'w')
    for ex in exs:
        for idx in range(0, len(ex)):
            prediction = classifier.predict(ex.tokens, idx)
            f.write(ex.tokens[idx] + " " + repr(int(prediction)) + "\n")
        f.write("\n")
    f.close()

if __name__ == '__main__':
    start_time = time.time()
    args = _parse_args()
    print(args)
    # Load the training and test data
    ## TODO: Change the dataset to the full dataset
    # train_class_exs = list(transform_for_classification(read_data("data/eng.train.small")))
    train_class_exs = list(transform_for_classification(read_data(args.train_path)))

    ## TODO: Change the dev set to the full dev set
    dev_class_exs = list(transform_for_classification(read_data(args.dev_path)))
    # dev_class_exs = list(transform_for_classification(read_data("data/eng.test.small")))
    ## TODO: Cleanup changes done for debugging: Uncomment training code
    # Train the model
    if args.model == "BAD":
        classifier = train_count_based_binary_classifier(train_class_exs)
    else:
        classifier = train_classifier(train_class_exs)
    print("Data reading and training took %f seconds" % (time.time() - start_time))

    ## Pickle dump for debugging
    # with open("./model/model_dump.pkl", "wb") as f:
    #     pickle.dump(classifier, f)
    # with open("./model/model_dump.pkl", "rb") as f:
    #     classifier = pickle.load(f)
    # Evaluate on training, development, and test data
    print("===Train accuracy===")
    ## TODO: Uncomment the training accuracy part
    evaluate_classifier(train_class_exs, classifier)
    print("===Dev accuracy===")
    evaluate_classifier(dev_class_exs, classifier)

    if args.run_on_test:
        print("Running on test")
        test_exs = list(transform_for_classification(read_data(args.blind_test_path)))
        predict_write_output_to_file(test_exs, classifier, args.test_output_path)
        print("Wrote predictions on %i labeled sentences to %s" % (len(test_exs), args.test_output_path))



