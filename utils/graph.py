import numpy as np
import os
from .utils import OpenAIEmbedder
from neo4j import GraphDatabase
import faiss
from py2neo import Graph
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import ast 
import tqdm

class Neo4jHandler:
    def __init__(self, uri:str = None, username:str = None, password:str = None):
        if not uri:
            self.uri = os.environ["NEO4J_URI"]
        
        if not username:
            self.username = os.environ["NEO4J_USERNAME"]

        if not password:
            self.password = os.environ["NEO4J_PASSWORD"]
            
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        self.embedder = OpenAIEmbedder()

        self.index = None
        self.node_ids = []
        
    def create_faiss_index(self):
        nodes = self.retrieve_all_nodes_with_embeddings()
        embeddings = [np.array(node[1]) for node in nodes]
        self.node_ids = [node[0] for node in nodes]
        dimension = len(embeddings[0])
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings))

    def retrieve_all_nodes_with_embeddings(self):
        cypher_query = """
            MATCH (n)
            WHERE n.embeddings IS NOT NULL
            RETURN elementId(n) AS id, n.embeddings AS embeddings
        """
        nodes = []
        with self.driver.session() as session:
            result = session.run(cypher_query)
            for record in result:
                nodes.append((record["id"], record["embeddings"]))
        return nodes
    
    def handle_query(self, query, distance=0.4):
        # Generate embedding for the query
        query_embedding = self.embedder.embed_text(query)
        query_vector = np.array(query_embedding).reshape(1, -1)
        

        if not self.index:
            self.create_faiss_index()

        # Perform FAISS search
        D, I = self.index.search(query_vector, 2)
        
        # print(f" Distance of nearest Embeddings: {D}")
        # print(f" Indices of nearest Embeddings: {I}")
        
        top_node_indices = I[0]
        top_similarities = D[0]
        
        # Filter nodes based on similarity threshold
        top_nodes = []
        for idx, similarity in zip(top_node_indices, top_similarities):
            if similarity <= distance:
                top_nodes.append(self.node_ids[idx])

        # print(top_nodes)

        related_nodes_and_relations = []
        for node in top_nodes:
            related_nodes_and_relations.append(self.retrace_path_and_visualize(node))
        
        return related_nodes_and_relations
    
    def retrive_all_likable_names(self, company_name, table:str = "Company"):
        with self.driver.session() as session:
            result = session.run(
                f"""MATCH (n:{table})
                WHERE n.name =~ "(?i).*{company_name}.*"
                RETURN elementId(n) as Id, n.name as name""")
            return [{'name' : record["name"], 'Id' : record["Id"]} for record in result]
    
    def retrace_path_and_visualize(self, element_ids):
        # Initialize the result dictionary
        result = {
            'CompanyName': None,
            'AuditorName': None,
            'ReportName': None,
            'ReportText': None,
            'Opinion': None,
            'AuditName': None,
            'AuditOpinion':None,
        }

        # Cypher query to get the path
        # forward relation
        query = """
            MATCH path = (n)-[*]->(m)
            WHERE elementId(n) = $element_ids
            RETURN nodes(path) AS nodes, relationships(path) AS relationships
        """
        
        nodes = []
        relationships = []
        
        # Run the query and retrieve paths
        paths = self.driver.session().run(query, element_ids=element_ids)
        for path in paths:
            nodes.extend(path['nodes'])
            relationships.extend(path['relationships'])

        #  print(f"\n After Forward Relationships: {relationships}")
        # Backward relation
        query = """
            MATCH path = (n)<-[*]-(m)
            WHERE elementId(n) = $element_ids
            RETURN nodes(path) AS nodes, relationships(path) AS relationships
        """
        
        # Run the query and retrieve paths
        paths = self.driver.session().run(query, element_ids=element_ids)
        for path in paths:
            nodes.extend(path['nodes'])
            relationships.extend(path['relationships'])
        
        # print(f"\nAfter Backward Relationships: {relationships}")

        # Extract relevant information
        for node in nodes:
            labels = list(node.labels)
            if 'Company' in labels:
                result['CompanyName'] = node['name']
            elif 'Auditor' in labels:
                result['AuditorName'] = node['name']
            elif 'Report' in labels:
                result['ReportName'] = node['name']
                result['ReportText'] = node['text']
            elif 'Opinion' in labels:
                result['Opinion'] = node['text']
            elif 'Audit' in labels:
                result['AuditName'] = node['name']
                result['AuditOpinion'] = node['audit_opinion']
        
        # Visualize the path
        G = nx.DiGraph()
        
        colors = ["LightSkyBlue","LightGreen","LightCoral","PeachPuff","Thistle", "LightSalmon","LightPink","PaleGoldenrod","LightYellow","Lavender"]
        node_colors = []
        edge_labels = {}

        def split_label(label, max_words_per_line=2):
            words = label.split(' ')
            lines = []
            for i in range(0, len(words), max_words_per_line):
                lines.append(' '.join(words[i:i + max_words_per_line]))
            return '\n'.join(lines)
        
        for relationship in relationships:
            start_node = relationship.start_node
            end_node = relationship.end_node
            start_node_label = list(start_node.labels)[0] 
            end_node_label = list(end_node.labels)[0] 
            start_label = f"{start_node_label} : {start_node['name']}" if start_node['name'] else start_node_label
            end_label = f"{end_node_label} : {end_node['name']}" if end_node['name'] else end_node_label
            G.add_edge(split_label(start_label), split_label(end_label))
            edge_labels[(split_label(start_label), split_label(end_label))] = relationship.type

        for i in range(len(G)):
            node_colors.append(colors[i % len(colors)])

        # pos = nx.spring_layout(G)  # For spring layout
        # pos = nx.circular_layout(G)  # For circular layout
        # pos = nx.shell_layout(G)  # For shell layout
        # pos = nx.kamada_kawai_layout(G)  # For Kamada-Kawai layout
        pos = nx.spectral_layout(G)  # For spectral layout

        plt.figure(figsize=(12, 8))
        nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=3000, edge_color='gray', font_size=8, font_weight='bold')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='red', font_size=7)

        plt.title('Data Path')
        # plt.show()
        
        file_name = f"{element_ids}.png"
        plt.savefig(file_name)
        result['Graph'] = file_name
        
        return result
    
    def close(self):
        self.driver.close()

    def clear_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def create_company_auditor_relationship(self, company_name, auditor_name):
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Company {name: $company_name}) "
                "MERGE (a:Auditor {name: $auditor_name}) "
                "MERGE (a)-[:AUDITS]->(c)",
                company_name=company_name, auditor_name=auditor_name
            )
            
    def create_company_report_relationship(self, company_name, report_name, report_text):
        embeddings = self.embedder.embed_text(report_text)
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Company {name: $company_name})"
                "MERGE (r:Report {name: $report_name, text: $report_text, embeddings: $embeddings})"
                "MERGE (c)-[:HAS_REPORT]->(r)",
                company_name=company_name, report_name=report_name, report_text=report_text, embeddings = embeddings
            )

    def create_report_opinion_relationship(self, report_name, report_text, opinion):
        report_embeddings = self.embedder.embed_text(report_text)
        opinion_embeddings = self.embedder.embed_text(opinion)

        with self.driver.session() as session:
            session.run(
                "MERGE (r:Report {name: $report_name, text: $report_text, embeddings: $report_embeddings})"
                "MERGE (o:Opinion {text: $opinion, embeddings: $opinion_embeddings})"
                "MERGE (r)-[:CONTAINS_OPINION]->(o)",
                report_name=report_name, report_text=report_text, report_embeddings = report_embeddings, opinion=opinion, opinion_embeddings = opinion_embeddings
            )

    def create_opinion_audit_relationship(self, opinion, audit_name, audit_opinion):
        audit_embeddings = self.embedder.embed_text(audit_name + audit_opinion)
        opinion_embeddings = self.embedder.embed_text(opinion)

        with self.driver.session() as session:
            session.run(
                "MERGE (o:Opinion {text: $opinion, embeddings: $opinion_embeddings})"
                "MERGE (a:Audit {name: $audit_name, audit_opinion: $audit_opinion, embeddings: $audit_embeddings})"
                "MERGE (o)-[:HAS_AUDIT]->(a)",
                audit_name=audit_name, audit_opinion=audit_opinion, audit_embeddings = audit_embeddings, opinion=opinion, opinion_embeddings = opinion_embeddings
            )


if __name__ == "__main__":

    if False:    
        # Reading the data from the Excel sheet.
        df = pd.read_excel('data/Final_Result_Top50.xlsx')

        Report = df['Report'].tolist()
        # Company_Names = df['Company Name'].tolist()
        # Opinion = df['Opinion'].tolist()
        # Audits = df['Audits'].tolist()
        
        # Extracting auditor from the Report
        auditor = [report.lower().split('/s/')[1].split('\n') for report in Report]
        auditor = [a[0].strip() if len(a[0]) > 2 else a[1].strip() for a in auditor]
        df['Auditor'] = auditor

        #Extracting Report Name from the Report
        report_name = [report.split('\n')[0] if len(report.split('\n')[0]) > 2 else report.split('\n')[1] for report in df['Report']]
        df['Report_Name'] = report_name
        
        #Converting the audit str -> dict
        df['Audits'] = df['Audits'].apply(lambda x: ast.literal_eval(x))


        #Creating an Instance of the class
        neo4j_handler = Neo4jHandler()

        #Clearing the database
        neo4j_handler.clear_database()

        #Populating the database with the data. 
        for index, row in tqdm(df.iterrows(), total=len(df)):
            company_name = row['Company Name']
            auditor_name = row['Auditor']
            report_name = row['Report_Name']
            report_text = row['Report']
            opinion = row['Opinion']
            audits = row['Audits']

            
            # Create Company-Auditor relationship
            neo4j_handler.create_company_auditor_relationship(company_name, auditor_name)

            # Create Company-Report relationship
            neo4j_handler.create_company_report_relationship(company_name, report_name, report_text)
            
            # Create Report-Opinion relationship
            neo4j_handler.create_report_opinion_relationship(report_name, report_text, opinion)

            # Create Report-Audit relationships
            for audit in audits:
                audit_name = audit['Audit_Name']
                audit_opinion = audit['Audit_Opinion']
                neo4j_handler.create_opinion_audit_relationship(opinion, audit_name, audit_opinion)

        # Close the Neo4j handler
        neo4j_handler.close()
    else:
        #Creating an Instance of the class
        neo4j_handler = Neo4jHandler()

        neo4j_handler.retrive_all_likable_names(company_name="Delloite")
        print("\n Connected accurately.")
        # Close the Neo4j handler
        neo4j_handler.close()
