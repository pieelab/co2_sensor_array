# > rsconnect::deployApp('~/repos/co2_sensor_array/shiny/co2_sensors/')

library(shiny)
library(dplyr)
library(data.table)
library(ggplot2)
library(lubridate)
library(plotly)
library(RMariaDB)

get_co2_data <- function(date_range){
    con <- DBI::dbConnect(RMariaDB::MariaDB(),
                          host = "remotemysql.com",
                          user = "rgDubOKpGu",
                          password = "qK7Ymofmms",
                          dbname = "rgDubOKpGu"
    )
    t <- Sys.time()
    local_t <- sprintf("%02d:%02d:%02d",hour(t),minute(t),round(second(t)))
    local_tz_datetime <- lubridate::ymd_hms(paste(date_range, local_t), tz=Sys.timezone())    
    select_datetime_range <- with_tz(local_tz_datetime, "UTC")
    d1 <- select_datetime_range[1]
    d2 <- select_datetime_range[2]
    tables <- RMariaDB::dbListTables(con)
    select_tables <- function(con,name){
        tb <- RMariaDB::dbGetQuery(con, sprintf("SELECT * FROM %s WHERE T BETWEEN '%s' AND '%s'", name, d1, d2))
        out <- as.data.table(tb)
        out[,device_id := name]
        out[,CO2_ppm := PPM_10X/10]
        out[,sensor_id := as.factor(SENSOR)]
        
    }
    dt <- rbindlist(lapply(tables, select_tables, con=con))
    DBI::dbDisconnect(con) 
    dt 
}

# Define UI for application that draws a histogram
ui <- fluidPage(

    # Application title
    titlePanel("CO2 Sensor Data"),

    # Sidebar with a slider input for number of bins 
    sidebarLayout(
        sidebarPanel(
            dateRangeInput("dates", "Date range", start = Sys.Date() - 2, end = Sys.Date(), min = NULL,
                           max = Sys.Date(), format = "yyyy-mm-dd", startview = "month", weekstart = 0,
                           language = "en", separator = " to ", width = NULL)
        ),

        # Show a plot of the generated distribution
        mainPanel(
            plotlyOutput("distPlot")
        ),
        
    )
)

# Define server logic required to draw a histogram
server <- function(input, output) {

    output$distPlot <- renderPlotly({
        # generate bins based on input$bins from ui.R
        dt <- get_co2_data(input$dates)
        pl <- ggplot(dt, aes(T,CO2_ppm, colour=sensor_id)) + geom_line() +facet_grid(device_id ~ .) 
        ggplotly(pl)
    })
    output$dateText  <- renderText({
        paste("input$date is", as.character(input$dates))
    })
}

# Run the application 
shinyApp(ui = ui, server = server)
