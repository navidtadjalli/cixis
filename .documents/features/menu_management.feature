Feature: Menu management
  Owner maintains products and publishes the QR menu.

  Scenario: Owner adds new product
    Given owner علی is on the menu management screen
    And no product named اسپرسو exists
    When علی adds product اسپرسو with price 120000 in category نوشیدنی گرم
    Then اسپرسو is shown in the menu management screen
    And اسپرسو costs 120000
    And اسپرسو is active

  Scenario: Owner changes product price
    Given owner علی is on the menu management screen
    And اسپرسو exists with price 120000
    When علی changes the price of اسپرسو to 140000
    Then اسپرسو costs 140000 in the menu management screen

  Scenario: Owner marks product as unavailable
    Given owner علی is on the menu management screen
    And اسپرسو is active
    When علی marks اسپرسو as unavailable
    Then اسپرسو is inactive
    And staff cannot add اسپرسو to a new order

  Scenario: Owner publishes menu to QR server
    Given owner علی is on the menu management screen
    And اسپرسو is active with price 120000
    When علی publishes the menu to the QR server
    Then the QR server receives اسپرسو with price 120000
    And the publish status is successful

  Scenario: Inactive products excluded from QR menu
    Given owner علی is on the menu management screen
    And اسپرسو is active
    And موکا is inactive
    When علی publishes the menu to the QR server
    Then the QR menu includes اسپرسو
    And the QR menu does not include موکا
