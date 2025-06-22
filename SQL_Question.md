1. What is the difference between an INNER JOIN and a LEFT JOIN in SQL?

Both INNER JOIN and LEFT JOIN (also known as LEFT OUTER JOIN) are used to combine rows from two or more tables based on a related column between them. The key difference lies in how they handle non-matching rows.

    INNER JOIN:

        Purpose: Returns only the rows where there is a match in both tables based on the join condition.

        Behavior: If a row from the left table does not have a corresponding match in the right table (or vice-versa), that row will be excluded from the result set.

        Analogy: Think of it as finding the "intersection" of two sets. Only elements present in both sets are included.
Example:

SELECT Orders.OrderID, Customers.CustomerName
FROM Orders
INNER JOIN Customers ON Orders.CustomerID = Customers.CustomerID;
LEFT JOIN (or LEFT OUTER JOIN):

    Purpose: Returns all rows from the left table, and the matching rows from the right table. If there's no match in the right table, NULL values are returned for the columns from the right table.

    Behavior: Every row from the left table is included in the result.

    Analogy: Think of it as keeping everything from the "left" list, and trying to find corresponding items in the "right" list. If a match is found, include it; otherwise, just mark the right-side details as empty (NULL).
Example:

SELECT Customers.CustomerName, Orders.OrderID
FROM Customers
LEFT JOIN Orders ON Customers.CustomerID = Orders.CustomerID;
2. Explain how transactions work in PostgreSQL. How would you implement a rollback mechanism?

In PostgreSQL (and most relational databases), a transaction is a sequence of operations performed as a single logical unit of work. The core concept behind transactions is the ACID properties:

    Atomicity: All operations within a transaction are treated as a single, indivisible unit. Either all of them succeed (commit), or none of them do (rollback). There's no partial completion.

    Consistency: A transaction brings the database from one valid state to another valid state. It must ensure that any data written to the database is valid according to defined rules (constraints, triggers, etc.).

    Isolation: Concurrent transactions execute independently of each other. The intermediate state of one transaction is not visible to other transactions until it is committed. This prevents anomalies like dirty reads, non-repeatable reads, and phantom reads.

    Durability: Once a transaction has been committed, its changes are permanent and will survive system failures (e.g., power outages, crashes).

How Transactions Work in PostgreSQL:

    BEGIN or START TRANSACTION: This statement explicitly starts a new transaction block. All subsequent SQL statements until COMMIT or ROLLBACK will be part of this transaction.

    SQL Statements: You execute your DML (Data Manipulation Language) statements like INSERT, UPDATE, DELETE, and DDL (Data Definition Language) statements like CREATE TABLE, ALTER TABLE.

    COMMIT: If all operations within the transaction are successful and you want to make the changes permanent, you issue COMMIT. The changes are then written to the disk, and the transaction is ended.

    ROLLBACK: If an error occurs, or you decide for any reason not to make the changes permanent, you issue ROLLBACK. All changes made since the BEGIN statement are undone, and the database reverts to its state before the transaction started. The transaction is then ended.

Implicit Transactions: If you don't explicitly start a transaction with BEGIN, each SQL statement in PostgreSQL runs as its own transaction (auto-commit mode). This means each statement is automatically committed upon successful completion.

Implementing a Rollback Mechanism:

The rollback mechanism is inherent to the transaction itself. You don't "implement" rollback as a separate piece of code, but rather you use the ROLLBACK command within the context of a transaction when something goes wrong.
Here's a conceptual example using SQL and Python (using psycopg2 for PostgreSQL):

SQL Example:

-- Start a transaction
BEGIN;

-- Attempt to insert data into two tables
INSERT INTO products (product_name, price) VALUES ('Laptop', 1200.00);
INSERT INTO orders (product_id, quantity) VALUES (1, 10); -- Assume product_id 1 is the new laptop

-- Now, imagine an error occurs, e.g., trying to insert into a non-existent table,
-- or a constraint violation (e.g., duplicate primary key, invalid foreign key).
-- For demonstration, let's simulate a failure:
-- INSERT INTO non_existent_table (col) VALUES (1);

-- If everything went well, you would commit:
-- COMMIT;

-- If an error occurred or you want to undo, you would rollback:
ROLLBACK;
3. How would you use Django ORM to run raw SQL queries in PostgreSQL? Provide an example.

Django ORM primarily provides an abstraction layer to interact with your database using Python objects. However, there are scenarios where you need the power and flexibility of raw SQL, for example:

    Performing complex queries that are difficult or inefficient to express with the ORM.

    Using database-specific features not exposed by the ORM (e.g., advanced window functions, specific functions).

    Optimizing performance for very specific operations.

    Running DDL statements not supported by migrations.

Django provides several ways to run raw SQL queries:

    Model.objects.raw(): For executing raw SELECT queries that map to model fields. The result is a RawQuerySet that behaves like a normal QuerySet in many ways (e.g., can be iterated).

    django.db.connection.cursor(): For executing arbitrary SQL queries, including INSERT, UPDATE, DELETE, and DDL statements. This gives you full control but requires you to manage the results and potential errors more manually.

    QuerySet.extra() (Deprecated/Discouraged): Allows injecting extra clauses (SELECT, WHERE, ORDER BY) into ORM-generated SQL. Generally, prefer Model.objects.raw() or cursor() for raw SQL.

    QuerySet.annotate() / QuerySet.aggregate() with RawSQL: For injecting raw SQL expressions into SELECT statements, often used in conjunction with ORM methods.

Example using Model.objects.raw() and django.db.connection.cursor():

Let's assume you have a Django model like this:

# myapp/models.py
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

Scenario:

    You want to select products whose names are similar using PostgreSQL's SIMILAR TO operator, which is not directly available in Django ORM.

    You want to perform a batch UPDATE that calculates a new price based on existing data, or a complex INSERT that Django ORM might not handle simply.
4. Explain the benefits of using JSON fields in PostgreSQL.
PostgreSQL offers two types of JSON fields: json and jsonb. While json stores the exact text representation of the JSON input, jsonb (JSON Binary) is generally preferred due to its numerous benefits:

jsonb (JSON Binary) Benefits:

    Efficient Storage & Faster Processing:

        jsonb stores JSON data in a decomposed binary format, which is more efficient for querying and indexing than the plain text json type.

        It removes insignificant whitespace, reorders keys, and removes duplicate keys, leading to optimized storage and faster parsing.

    Indexing Capabilities:

        You can create GIN (Generalized Inverted Index) indexes on jsonb columns. This allows for very fast querying of keys, values, or specific elements within the JSON document. For example, you can quickly find all documents where a specific JSON key exists or has a particular value.

        This is a significant advantage over storing JSON in a TEXT field and parsing it at query time.

    Powerful Querying Functions & Operators:

        PostgreSQL provides a rich set of operators and functions specifically designed for jsonb manipulation and querying (e.g., ->, ->>, #>, #>>, ?, ?|, ?&, @>, <@, -).

        These allow you to:

            Extract specific values by key or path.

            Check for the existence of keys or values.

            Perform containment checks (e.g., does this JSON document contain this smaller JSON fragment?).

            Append to arrays, delete keys, and update values.

    Flexibility and Schema Evolution:

        JSON fields provide a schemaless or flexible schema approach. You don't need to define every column beforehand. This is invaluable when dealing with data whose structure is dynamic, evolving, or highly variable (e.g., user preferences, product attributes, event logs, configuration data).

        You can add new attributes to your data without performing schema migrations, which simplifies development and deployment, especially in rapidly changing environments.

    Reduced Table Sprawl (Column Bloat):

        Instead of having dozens or hundreds of nullable columns for various attributes, you can consolidate them into a single jsonb column. This reduces table width, which can improve performance for queries that don't involve the JSON data, and makes table management simpler.

    Integration with Application Development:

        Many modern applications (especially web and mobile) often work with JSON data. Storing JSON directly in the database simplifies the impedance mismatch between the application's data structures and the database's storage model.

    Hybrid Approach (Relational + Document):

        jsonb allows you to combine the strengths of relational databases (strong typing, relationships, integrity for core data) with the flexibility of document-oriented databases (flexible schema for volatile or complex attributes) within a single system. You can store stable, critical data in regular columns and dynamic, less critical data in jsonb.

When to use jsonb vs. Normalized Columns:

    Use jsonb when:

        The data has a flexible or evolving schema.

        The attributes are numerous and frequently change.

        You need to store unstructured or semi-structured data.

        You primarily query for the existence of keys or values, or for containment within the JSON.

        The data is often consumed as a whole JSON object by your application.

    Use normalized columns when:

        The data has a stable, well-defined structure.

        You need strict data integrity and type checking.

        You frequently query specific individual attributes and perform complex joins on them.

        The attribute values are used as foreign keys or have unique constraints.

        Referential integrity is paramount.

In most cases, jsonb is the preferred choice over json due to its performance and indexing capabilities.
5. What is normalization? Explain 3NF.
Normalization is a systematic approach to organizing the columns and tables of a relational database to minimize data redundancy and improve data integrity. It involves decomposing a large table into smaller, well-structured tables and defining relationships between them.

The primary goals of normalization are:

    Eliminate Redundant Data: Avoid storing the same piece of information multiple times.

    Reduce Data Anomalies: Prevent update, insertion, and deletion anomalies.

        Update Anomaly: Changing data in one place requires changing it in multiple places. If one instance is missed, data becomes inconsistent.

        Insertion Anomaly: Cannot add new data without adding other, unrelated data.

        Deletion Anomaly: Deleting a row unintentionally deletes other, unrelated data.

    Improve Data Integrity: Ensure data is accurate and consistent.

    Simplify Queries: While sometimes leading to more joins, well-normalized data can simplify certain query types and improve maintainability.

Normalization is achieved through a series of "normal forms," with each form building upon the previous one, adding stricter rules to reduce redundancy and improve integrity. The most common normal forms are 1NF, 2NF, and 3NF.    

6.Database Shrading:
It is basically a database architecture pattern in which we split a large dataset into smaller chunks (logical shards) and we store/distribute these chunks in different machines/database nodes (physical shards).

    Each chunk/partition is known as a "shard" and each shard has the same database schema as the original database.
    We distribute the data in such a way that each row appears in exactly one shard.
    It's a good mechanism to improve the scalability of an application. 
1. Key Based Sharding

Key Based Sharding is a technique is also known as hash-based sharding. Here, we take the value of an entity such as customer ID, customer email, IP address of a client, zip code, etc and we use this value as an input of the hash function. This process generates a hash value which is used to determine which shard we need to use to store the data.
2.Horizontal or Range Based Sharding 

In Horizontal or Range Based Sharding, we divide the data by separating it into different parts based on the range of a specific value within each record. Let's say you have a database of your online customers' names and email information. You can split this information into two shards.

    In one shard you can keep the info of customers whose first name starts with A-P
    In another shard, keep the information of the rest of the customers.     
3. Vertical Sharding

In Vertical Sharding, we split the entire column from the table and we put those columns into new distinct tables. Data is totally independent of one partition to the other ones. Also, each partition holds both distinct rows and columns. We can split different features of an entity in different shards on different machines.     
Advantages of Vertical Sharding:

    Query Performance: Vertical sharding can improve query performance by allowing each shard to focus on a specific subset of columns. This specialization enhances the efficiency of queries that involve only a subset of the available columns.
    Simplified Queries: Queries that require a specific set of columns can be simplified, as they only need to interact with the shard containing the relevant columns. 
Disadvantages of Vertical Sharding:

    Potential for Hotspots: Certain shards may become hotspots if they contain highly accessed columns, leading to uneven distribution of workloads.
    Challenges in Schema Changes: Making changes to the schema, such as adding or removing columns, may be more challenging in a vertically sharded system. Changes can impact multiple shards and require careful coordination.    