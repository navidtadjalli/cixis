Feature: Ordering
  Staff creates and edits orders for cafe tables.

  Scenario: Staff opens table and creates order
    Given staff سارا is on the tables screen
    And میز ۱ is empty
    When سارا opens میز ۱
    And سارا creates a new order
    Then میز ۱ has an active order
    And the order total is 0

  Scenario: Staff adds multiple items to order
    Given staff سارا has opened an active order for میز ۱
    And اسپرسو costs 120000
    And کیک شکلاتی costs 180000
    When سارا adds 1 اسپرسو to the order
    And سارا adds 2 کیک شکلاتی to the order
    Then the order contains 1 اسپرسو
    And the order contains 2 کیک شکلاتی
    And the order total is 480000

  Scenario: Staff changes item quantity
    Given staff سارا has opened an active order for میز ۱
    And the order contains 1 اسپرسو at 120000
    When سارا changes the quantity of اسپرسو to 3
    Then the order contains 3 اسپرسو
    And the order total is 360000

  Scenario: Staff removes item before payment
    Given staff سارا has opened an active order for میز ۱
    And the order contains 1 اسپرسو at 120000
    And the order contains 1 لاته at 150000
    And no payment has been recorded for the order
    When سارا removes لاته from the order
    Then the order contains 1 اسپرسو
    And the order does not contain لاته
    And the order total is 120000

  Scenario: Price snapshot preserved after product price change
    Given staff سارا has opened an active order for میز ۱
    And اسپرسو costs 120000
    When سارا adds 1 اسپرسو to the order
    And owner علی changes the menu price of اسپرسو to 140000
    Then the order line for اسپرسو still has unit price 120000
    And the order total is 120000
