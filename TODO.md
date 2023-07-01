## List of tasks:

- [x] Enhance product service
    - [x] Delete product rpc call
    - [x] Wire into smoketest.sh
    - [x] Wire into perf-test
    - [x] Wire unit-test for this method
- [x] Enhance order service
    - [x] List orders rpc call
    - [x] Wire into smoketest.sh
    - [x] Wire into perf-test
    - [x] Wire unit-test for this method
- [x] Execute performance test
- [x] Question 1: Why is performance degrading as the test run longer?
        Answer: As the test runs, the GET /orders and POST /orders endpoints are called multiple times. During the cycle of these requests, queries are made to the database that list all existing items. At first this data does not affect so much but as there is more data, the answers start to take longer. This causes the test to degrade.
- [x] Question 2: How do you fix it?
        Answer: To mitigate this issue, it is possible to reduce the number of times the "external" services are queried. It is possible to create a function that lists all the products based on a list of product IDs, returning all the data in just one query.
    - [ ] Fix it