Feature: Event mode
  Cafe staff handles event orders by person name instead of table.

  Scenario: Owner switches to event mode
    Given owner علی is on the settings screen
    And the cafe is in table mode
    When علی switches the cafe to event mode
    Then the order screen shows event orders
    And table selection is not required for new orders

  Scenario: Staff creates order for named person
    Given staff سارا is on the event orders screen
    And the cafe is in event mode
    When سارا creates an order for نرگس
    And سارا adds 1 لاته at 150000
    Then an active event order named نرگس exists
    And the order total is 150000

  Scenario: Staff pays and closes event order
    Given staff سارا has opened the active event order named نرگس
    And the order total is 150000
    When سارا records a cash payment of 150000
    Then the event order named نرگس is closed
    And the unpaid amount is 0
