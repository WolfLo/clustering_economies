import pandas as pd
import numpy as np
from collections import defaultdict

from sklearn.preprocessing import scale
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture, BayesianGaussianMixture
from sklearn import metrics
import hdbscan

from scipy.cluster import hierarchy
from fastcluster import linkage

from fancyimpute import KNN
from fancyimpute import MICE
from fancyimpute.bayesian_ridge_regression import BayesianRidgeRegression

import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.colors import rgb2hex, colorConverter
import seaborn as sns

# %matplotlib inline
# plt.style.use('seaborn-white')


class Preprocessing:
    def __init__(self, csv_path, varlist=None, verbose=False):
        '''
        path -- the string of the csv file representing our raw dataset
        varlist -- the list of strings
        '''
        # import the csv dataset as a pandas DataFrame
        self.df = pd.read_csv(csv_path)
        # change index (row labels)
        self.df = self.df.set_index('Country Code', verify_integrity=True)
        # only keep the variables(columns) selected by user
        if varlist:
            varlist = ['Country Name'] + varlist
            self.df = self.df[varlist]
        # convert all columns but Country Names to numeric type
        self.df.iloc[:, 1:] = \
            self.df.iloc[:, 1:].apply(pd.to_numeric, errors='coerce')
        # report poor features and selected_countries
        if verbose:
            print('MISSING VALUES FOR EACH FEATURE:')
            print(self.df.isnull().sum(), '\n')
            print('MISSING VALUES FOR EACH COUNTRY:')
            print(self.df.isnull().sum(axis=1).sort_values(ascending=False).T)

    # def drop_poor_columns(self, p):
    #     ''' Drop the columns of self.df with more than p (%) missing values'''
    #
    #     # create df with a the count of missing values for each column
    #     missing_df = pd.DataFrame(self.df.isnull().sum())
    #     # extract the names of columns with more than p (%) missing values
    #     poor_columns = missing_df.loc[missing_df[0] > p*len(self.df)].index
    #     # drop sparse columns
    #     self.df.drop(poor_columns, axis=1, inplace=True)
    #     return self.df, poor_columns

    def dropPoorFeatures(self, axis, p):
        '''
        Drop the rows/columns of self.df with more than p (%) missing values
        axis -- indicate whether to drop rows (axis=0) or columns(axis=1)
        '''
        # create df with the count of missing values for each row/column
        missing_df = pd.DataFrame(self.df.isnull().sum(axis=int(not axis)))
        # extract the names of rows/columns with more than p (%) missing values
        if axis == 0:
            length = len(self.df.columns)
        else:
            length = len(self.df)
        poor_features = missing_df.loc[missing_df[0] > p*length].index
        # drop sparse rows/columns
        self.df.drop(poor_features, axis=axis, inplace=True)
        return self.df, poor_features

    def imputeKNN(self):
        # df is my data frame with the missings. I keep only floats
        self.country_names = self.df['Country Name'].as_matrix()
        df_numeric = self.df.select_dtypes(include=[np.float64]).as_matrix()
        # impute missing values
        df_filled_KNN = pd.DataFrame(KNN(2).complete(df_numeric))
        df_filled_KNN.insert(
            loc=0, column='Country Names', value=self.country_names)
        df_filled_KNN.columns = self.df.columns
        df_filled_KNN.index = self.df.index
        return df_filled_KNN

    def exportCSV(self, path, impute=False):
        if not impute:
            # export the cleaned dataframe to a csv file
            self.df.to_csv(path)
        else:
            # impute the missing values before exporting to csv
            self.df = self.imputeKNN()
            self.df.to_csv(path)


class Clustering:
    def __init__(self, csv_path):
        self.df = pd.read_csv(csv_path)
        # change index (row labels)
        self.df = self.df.set_index('Country Code', verify_integrity=True)
        # df.info(verbose=False)
        # store country full names (for plots) before removing the feature
        self.country_names = self.df['Country Name'].as_matrix()
        self.df = self.df.drop(['Country Name'], axis=1)
        # scale the dataset to be distributed as a standard Gaussian
        cols = self.df.columns
        ind = self.df.index
        self.df = pd.DataFrame(scale(self.df))
        self.df.columns = cols
        self.df.index = ind
        # create disctionary of clusters
        self.clusterings = defaultdict(lambda: np.array(0))
        # print general info
        print('The imported dataset as the following characteristics:')
        print(self.df.info(verbose=False))

    def getPC(self):
        '''
        Calculate the principal components (PC) and create a new DataFrame
        by projecting the datapoints on the PC space.
        '''
        self.pca = PCA()
        self.df_pc = pd.DataFrame(
            self.pca.fit_transform(self.df), index=self.df.index)

        # plot the cumulated proportion of variance explained by the PC
        print('CUMULATIVE PROPORTION OF VARIANCE EXPLAINED BY PCs')
        plt.figure(figsize=(7, 5))

        plt.plot(range(1, len(self.pca.components_)+1),
                 self.pca.explained_variance_ratio_, '-o',
                 label='Individual component')
        plt.plot(range(1, len(self.pca.components_)+1),
                 np.cumsum(self.pca.explained_variance_ratio_), '-s',
                 label='Cumulative')

        plt.ylabel('Proportion of Variance Explained')
        plt.xlabel('Principal Component')
        plt.xlim(0.75, 4.25)
        plt.ylim(0, 1.05)
        plt.xticks(range(1, len(self.pca.components_)+1))
        plt.legend(loc=2)

    def plotAlongPC(self, pc1=0, pc2=1, xlim=[-5, 5], ylim=[-5, 5]):
        '''
        Plot the countries along the two principal components given in input:
        pc1[int] (usually = 0, indicating the first PC) and pc2[int]
        '''
        fig, ax1 = plt.subplots(figsize=(9, 7))

        ax1.set_xlim(xlim[0], xlim[1])
        ax1.set_ylim(ylim[0], ylim[1])

        # Plot Principal Components pc1 and pc2
        for i in self.df_pc.index:
            ax1.annotate(i,
                         (self.df_pc[pc1].loc[i], -self.df_pc[pc2].loc[i]),
                         ha='center')

        # Plot reference lines
        ax1.hlines(0, -5, 5, linestyles='dotted', colors='grey')
        ax1.vlines(0, -5, 5, linestyles='dotted', colors='grey')
        pc1_string = 'Principal Component ' + str(pc1)
        pc2_string = 'Principal Component ' + str(pc2)
        ax1.set_xlabel(pc1_string)
        ax1.set_ylabel(pc2_string)
        return

    def plotDendrogram(self, links, threshold, metric, method):
        plt.figure(figsize=(15, 9))
        den_title = 'METHOD: ' + str(method) + ' METRIC: ' + str(metric)
        plt.title(den_title)
        den = hierarchy.dendrogram(links,
                                   orientation='right',
                                   labels=self.country_names,
                                   color_threshold=threshold,
                                   leaf_font_size=10)
        plt.vlines(threshold, 0,
                   plt.gca().yaxis.get_data_interval()[1],
                   colors='r', linestyles='dashed')

        return den

    def clustersTable(self, clustering):
        '''
        Clustering is an array of cluster labels, one for each country
        '''
        lis = sorted(
            list(zip(clustering, self.country_names)), key=lambda x: x[0])
        groups = set(map(lambda x: x[0], lis))
        table = pd.DataFrame(list(
            zip(groups, [[y[1] for y in lis if y[0] == x] for x in groups])))
        table.columns = ['Cluster', '']
        table.set_index('Cluster', inplace=True, verify_integrity=False)
        return table

    def hierarchicalClustering(
            self, metric, method, threshold=None, on_PC=0):
        '''
        Show figures of clusters retrieved through the hierachical method
        and return an array with the cluster index of each country.

        metric -- [str] used for assigning distances to data:
                   'euclidean', 'ćorrelation', 'cosine', 'seuclidean'...
        method -- [str] the type of linkage used for agglomerating the nodes
                    'average','complete','ward'...(check fastcluster full list)
        threshold -- [int] threshold distance for separing clusters,
                     in the hierachical tree.
        on_PC -- [int] apply clustering by using data projections
                 on the first on_PC principal components
        '''
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df

        if method == 'all':
            method = ['average',
                      'complete',
                      'single',
                      'weighted',
                      'centroid',  # only for Euclidean data
                      'median',  # only for Euclidean data
                      'ward',  # only for Euclidean data
                      ]
        elif type(method) != list:
            method = list([method])
        metric = str(metric)

        print('Hierarchical clustering with', metric, 'distance metric.')
        for met in method:
            # set up the linking tool
            links = linkage(df, metric=metric, method=met)
            self.link = links
            # plot dendrogram
            self.plotDendrogram(links, threshold, metric, met)
            cmap = sns.cubehelix_palette(
                as_cmap=True, start=.5, rot=-.75, light=.9)
            sns.clustermap(
                data=df, row_linkage=links, col_cluster=False, cmap=cmap)
            # store tables of clusters for each clustering method used
            clustering_name = 'hierarchical_' + str(met) + '_' + str(metric)
            self.clusterings[clustering_name] = self.clustersTable(
                hierarchy.fcluster(links, threshold, criterion='distance'))

        # self.hierarchical_classes = get_hierarchical_classes(den)
        # plt.savefig('tree2.png')

    def hdbscan(self, min_cluster_size=2, on_PC=0):
        '''compute clusters using HDBSCAN algorithm'''
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df
        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
        clusterer.fit_predict(df)
        self.clusterings['hdbscan'] = self.clustersTable(clusterer.labels_)

    def bayesianGaussianMixture(self, n_components, covariance_type='full',
                    n_init=50, on_PC=0):
        '''
        Compute Bayesian Gaussian Mixture clustering.
        Note: in this case, the number of components effectively used
        can be < n_componentss (at most, n_components).
        '''
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df
        clusterer = BayesianGaussianMixture(n_components,
                                            covariance_type=covariance_type,
                                            n_init=n_init)
        labels = clusterer.fit(df).predict(df)
        self.clusterings['bayesian gm' + str(n_components)] = \
            self.clustersTable(labels)

    def gaussianMixture(self, n_components, covariance_type='full',
                        n_init=50, on_PC=0):
        '''compute Gaussian Mixture clustering'''
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df
        clusterer = GaussianMixture(n_components,
                                    covariance_type=covariance_type,
                                    n_init=n_init)
        labels = clusterer.fit(df).predict(df)
        self.clusterings['gm' + str(n_components)] = \
            self.clustersTable(labels)

    def gmBIC(self, n_min, n_max, covariance_type='full',
                n_init=50, on_PC=0):
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df
        '''compute Bayesian Information Criterion'''
        n_components = np.arange(n_min, n_max)
        models = [
            GaussianMixture(n, covariance_type=covariance_type, n_init=n_init)
            for n in n_components]
        bics = [model.fit(df).bic(df) for model in models]
        bics = np.array(bics)
        # store the optimal number of gaussian components and the resulting BIC
        self.min_BIC = [bics.argmin()+1, bics.min()]
        plt.plot(n_components, bics)
        print('the minimum BIC is achieved with \
              %i gaussian components' % self.min_BIC[0])

    def kmeans(self, n_clusters=2, on_PC=0, n_init=50, evaluate=True):
        '''compute clusters using KMeans algorithm'''
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df
        # re-initialize seed for random initial centroids' position
        np.random.seed(42)
        clusterer = KMeans(n_clusters=n_clusters, n_init=n_init)
        clusterer.fit_predict(df)
        self.clusterings['kmeans' + str(n_clusters)] = \
            self.clustersTable(clusterer.labels_)
        # compute Silhouette and Calinski-Harabaz Score
        if evaluate:
            benchClustering(clusterer, 'kmeans', df)

    def multipleKmeans(self, k_min, k_max, on_PC=0, n_init=50):
        if on_PC > 0:
            df = self.df_pc.iloc[:, :on_PC+1]
        else:
            df = self.df

        ks = np.arange(k_min, k_max)
        silh = np.zeros(k_max - k_min)
        cal_har = np.zeros(k_max - k_min)
        for k in ks:
            # re-initialize seed for random initial centroids' position
            np.random.seed(42)
            clusterer = KMeans(n_clusters=k, n_init=n_init)
            clusterer.fit_predict(df)
            self.clusterings['kmeans' + str(k)] = \
                self.clustersTable(clusterer.labels_)
            silh[k-k_min] = metrics.silhouette_score(
                df, clusterer.labels_, metric='euclidean')
            cal_har[k-k_min] = metrics.calinski_harabaz_score(
                df, clusterer.labels_)

        # multiple line plot
        fig, ax1 = plt.subplots()
        color = 'green'
        ax1.set_xlabel('Number of clusters')
        ax1.set_ylabel('Silhouette Score', color=color)
        plt.plot(ks, silh, marker='o', markerfacecolor=color,
                 markersize=6, color=color, linewidth=2)

        ax2 = ax1.twinx()
        color = 'orange'
        ax2.set_ylabel('Calinski-Harabaz Score', color=color)
        plt.plot(ks, cal_har, marker='o', markerfacecolor=color,
                 markersize=6, color=color, linewidth=2)
        ax1.grid(True)
        plt.legend()

        return silh, cal_har


def plotBarh(df, by_column):

    by_column = str(by_column)
    newdf = df.sort_values(by=[by_column])
    x = np.array(newdf[by_column])
    y = np.array(newdf['Country Name'])
    y_pos = np.arange(len(y))

    fig, ax = plt.subplots(figsize=(5, 10))

    ax.set_yticks(y_pos)
    ax.set_yticklabels(y)
    ax.invert_yaxis()  # labels read top-to-bottom
    # ax.set_xlabel('%GDP')
    ax.set_title(by_column)

    ax.barh(y_pos, x)

def benchClustering(estimator, name, data):
    silh = metrics.silhouette_score(
        data, estimator.labels_, metric='euclidean')
    cal_har = metrics.calinski_harabaz_score(data, estimator.labels_)
    return silh, cal_har


def clusterScatter(x, y, z, clusters=None):
    x, y, z = np.random.random((3, 10000))

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    if clusters:
        colors = clusters
    else:
        color = 'green'

    ax.scatter(x,y,z, marker="o", c=clusters, s=40, cmap="RdBu")
    plt.show()
